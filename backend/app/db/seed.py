"""Database Seeder Script for Arloraka Coffee.

Reads master and transaction CSVs from the DS team (database/seed/) and inserts:
1. Management user (admin@arloraka.com / admin123)
2. 10 Freelancer users (FL-001..FL-010 / freelancer123)
3. 6 Master products (PRD-001..PRD-006)
4. 750 Sales reports and their line items (idempotent, skips if source_transaction_id exists)

Usage:
    python -m app.db.seed
"""

import asyncio
import csv
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.calculation import calculate_commission, calculate_management_share
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.product import Product
from app.models.report import Report, ReportItem, ReportStatus
from app.models.user import User, UserRole

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
SEED_DIR = BASE_DIR / "database" / "seed"


async def seed_data():
    print(f"[*] Looking for seed CSV files in: {SEED_DIR}")
    if not SEED_DIR.exists():
        print(f"[!] Directory not found: {SEED_DIR}")
        return

    # 1. Pastikan tabel terbuat di database
    print("[*] Creating tables in database if not exists...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # -------------------------------------------------------------
        # 2. Seed Management User
        # -------------------------------------------------------------
        admin_email = "admin@arloraka.com"
        res = await session.execute(select(User).where(User.email == admin_email))
        admin = res.scalar_one_or_none()
        if not admin:
            admin = User(
                name="Manajemen Arloraka",
                email=admin_email,
                hashed_password=get_password_hash("admin123"),
                role=UserRole.MANAGEMENT,
                is_active=True,
            )
            session.add(admin)
            await session.flush()
            print(f"[+] Admin created: {admin_email} (password: admin123)")

        # -------------------------------------------------------------
        # 3. Seed Freelancers (from freelancers.csv)
        # -------------------------------------------------------------
        freelancers_file = SEED_DIR / "freelancers.csv"
        user_code_map = {}  # "FL-001" -> User.id
        if freelancers_file.exists():
            with open(freelancers_file, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fl_code = row["freelancer_id"]
                    name = row["display_name"]
                    email = f"{name.lower()}@freelance.arloraka.com"

                    user_res = await session.execute(
                        select(User).where(User.freelancer_code == fl_code)
                    )
                    user = user_res.scalar_one_or_none()
                    if not user:
                        user = User(
                            name=name,
                            email=email,
                            freelancer_code=fl_code,
                            hashed_password=get_password_hash("freelancer123"),
                            role=UserRole.FREELANCER,
                            is_active=row.get("is_active", "True").lower() == "true",
                        )
                        session.add(user)
                        await session.flush()
                        print(f"[+] Freelancer seeded: {name} ({fl_code}) - {email}")
                    user_code_map[fl_code] = user.id
            await session.commit()

        # -------------------------------------------------------------
        # 4. Seed Products (from products.csv)
        # -------------------------------------------------------------
        products_file = SEED_DIR / "products.csv"
        product_code_map = {}  # "PRD-001" -> Product.id
        if products_file.exists():
            with open(products_file, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    prd_code = row["product_id"]
                    name = row["product_name"]
                    price = int(row["current_price"])

                    p_res = await session.execute(
                        select(Product).where(Product.product_code == prd_code)
                    )
                    product = p_res.scalar_one_or_none()
                    if not product:
                        product = Product(
                            product_code=prd_code,
                            name=name,
                            price=price,
                            description=f"Varian resmi {name}",
                            is_active=row.get("is_active", "True").lower() == "true",
                        )
                        session.add(product)
                        await session.flush()
                        print(f"[+] Product seeded: {name} (Rp {price:,})")
                    product_code_map[prd_code] = product.id
            await session.commit()

        # -------------------------------------------------------------
        # 5. Read Report Items first into a lookup dictionary
        # -------------------------------------------------------------
        items_file = SEED_DIR / "sales_report_items.csv"
        items_by_report = {}
        if items_file.exists():
            with open(items_file, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_id = row["report_id"]
                    if r_id not in items_by_report:
                        items_by_report[r_id] = []
                    items_by_report[r_id].append(
                        {
                            "product_id": row["product_id"],
                            "quantity": int(row["quantity"]),
                            "unit_price": int(row["unit_price_at_sale"]),
                        }
                    )

        # -------------------------------------------------------------
        # 6. Seed Sales Reports (from sales_reports.csv)
        # -------------------------------------------------------------
        reports_file = SEED_DIR / "sales_reports.csv"
        if reports_file.exists():
            print("[*] Seeding 750 transactions into database...")
            inserted_count = 0
            with open(reports_file, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trx_id = row["source_transaction_id"]
                    # Cek idempoten agar tidak ada data ganda
                    existing = await session.execute(
                        select(Report).where(Report.source_transaction_id == trx_id)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    fl_code = row["freelancer_id"]
                    freelancer_user_id = user_code_map.get(fl_code)
                    if not freelancer_user_id:
                        continue

                    sale_date_str = row["sale_date"]
                    sale_date = datetime.strptime(sale_date_str, "%Y-%m-%d").replace(
                        tzinfo=UTC
                    )

                    gross_amount = int(row["gross_amount"])
                    commission = calculate_commission(gross_amount)
                    mgmt_share = calculate_management_share(gross_amount, commission)

                    report = Report(
                        freelancer_id=freelancer_user_id,
                        source_transaction_id=trx_id,
                        report_date=sale_date,
                        status=ReportStatus(row["status"].lower()),
                        total_bottles=int(row["total_bottles"]),
                        total_omzet=gross_amount,
                        commission_amount=commission,
                        management_share=mgmt_share,
                        payment_method=row.get("payment_method"),
                        sale_location=row.get("sale_location"),
                        notes=row.get("notes") or None,
                    )
                    session.add(report)
                    await session.flush()

                    # Tambah items
                    for item_data in items_by_report.get(row["report_id"], []):
                        db_product_id = product_code_map.get(item_data["product_id"])
                        if db_product_id:
                            item_obj = ReportItem(
                                report_id=report.id,
                                product_id=db_product_id,
                                quantity=item_data["quantity"],
                                unit_price=item_data["unit_price"],
                                subtotal=item_data["quantity"]
                                * item_data["unit_price"],
                            )
                            session.add(item_obj)

                    inserted_count += 1
                    if inserted_count % 150 == 0:
                        print(f"    -> Progress: {inserted_count} reports seeded...")

            await session.commit()
            print(f"[✔] Successfully seeded {inserted_count} new transactions!")

    await engine.dispose()
    print("[✔] Database Seeding Finished Successfully!")


if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed_data())
