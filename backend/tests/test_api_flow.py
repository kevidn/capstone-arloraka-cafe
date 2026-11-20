import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_capstone_business_flow(client: AsyncClient):
    # -------------------------------------------------------------
    # 1. Register Manajemen & Freelancer
    # -------------------------------------------------------------
    mgmt_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Manajer Arloraka",
            "email": "manager@arloraka.com",
            "password": "managerpassword123",
            "role": "management",
        },
    )
    assert mgmt_reg.status_code == 201

    free_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Freelancer Budi",
            "email": "budi@freelance.com",
            "password": "budipassword123",
            "role": "freelancer",
        },
    )
    assert free_reg.status_code == 201
    freelancer_id = free_reg.json()["id"]

    # -------------------------------------------------------------
    # 2. Login & Token
    # -------------------------------------------------------------
    mgmt_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "manager@arloraka.com", "password": "managerpassword123"},
    )
    assert mgmt_login.status_code == 200
    mgmt_token = mgmt_login.json()["access_token"]
    mgmt_headers = {"Authorization": f"Bearer {mgmt_token}"}

    free_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "budi@freelance.com", "password": "budipassword123"},
    )
    assert free_login.status_code == 200
    free_token = free_login.json()["access_token"]
    free_headers = {"Authorization": f"Bearer {free_token}"}

    # -------------------------------------------------------------
    # 3. RBAC: Freelancer TIDAK BISA tambah produk
    # -------------------------------------------------------------
    forbidden_prod = await client.post(
        "/api/v1/products",
        json={"name": "Ilegal Product", "price": 15000},
        headers=free_headers,
    )
    assert forbidden_prod.status_code == 403

    # Manajemen tambah produk resmi
    prod_res = await client.post(
        "/api/v1/products",
        json={
            "name": "Kopi Susu Gula Aren 250ml",
            "price": 18000,
            "description": "Best seller botol 250ml",
        },
        headers=mgmt_headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # -------------------------------------------------------------
    # 4. Freelancer kirim laporan penjualan baru
    #    Beli 10 botol @18.000 = 180.000
    #    Komisi 10% = 18.000
    # -------------------------------------------------------------
    report_res = await client.post(
        "/api/v1/reports",
        json={
            "items": [{"product_id": product_id, "quantity": 10}],
        },
        headers=free_headers,
    )
    assert report_res.status_code == 201
    report_data = report_res.json()
    report_id = report_data["id"]
    assert report_data["freelancer_id"] == freelancer_id
    assert report_data["status"] == "pending"
    assert report_data["total_bottles"] == 10
    assert report_data["total_omzet"] == 180000
    assert report_data["commission_amount"] == 18000
    assert report_data["management_share"] == 162000

    # -------------------------------------------------------------
    # 5. Upload bukti transaksi
    # -------------------------------------------------------------
    dummy_file = ("nota.jpg", b"fake-jpeg-image-binary-data", "image/jpeg")
    upload_res = await client.post(
        f"/api/v1/reports/{report_id}/proofs",
        files={"file": dummy_file},
        headers=free_headers,
    )
    assert upload_res.status_code == 201
    assert upload_res.json()["file_name"] == "nota.jpg"

    # -------------------------------------------------------------
    # 6. Manajemen minta revisi
    # -------------------------------------------------------------
    verify_rev = await client.patch(
        f"/api/v1/reports/{report_id}/verify",
        json={
            "status": "revision",
            "revision_notes": "Tolong cek lagi jumlah botol, di nota tertera 12 botol.",
        },
        headers=mgmt_headers,
    )
    assert verify_rev.status_code == 200
    assert verify_rev.json()["status"] == "revision"
    assert "12 botol" in verify_rev.json()["revision_notes"]

    # -------------------------------------------------------------
    # 7. Freelancer perbaiki laporan revisi (PAKAI ID SAMA)
    #    Update jadi 12 botol @18.000 = 216.000
    #    Komisi 10% = 21.600
    # -------------------------------------------------------------
    rev_res = await client.put(
        f"/api/v1/reports/{report_id}/revision",
        json={
            "items": [{"product_id": product_id, "quantity": 12}],
        },
        headers=free_headers,
    )
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["id"] == report_id  # ID tetap sama persis!
    assert rev_data["status"] == "pending"  # Kembali pending untuk verifikasi ulang
    assert rev_data["total_bottles"] == 12
    assert rev_data["total_omzet"] == 216000
    assert rev_data["commission_amount"] == 21600
    assert rev_data["management_share"] == 194400

    # -------------------------------------------------------------
    # 8. Manajemen menyetujui (Approve) laporan
    # -------------------------------------------------------------
    verify_app = await client.patch(
        f"/api/v1/reports/{report_id}/verify",
        json={"status": "approved", "revision_notes": "Sudah sesuai."},
        headers=mgmt_headers,
    )
    assert verify_app.status_code == 200
    assert verify_app.json()["status"] == "approved"

    # -------------------------------------------------------------
    # 9. Verifikasi detail & perlindungan akses antarpengguna
    # -------------------------------------------------------------
    detail = await client.get(f"/api/v1/reports/{report_id}", headers=free_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "approved"
    assert len(detail.json()["proofs"]) >= 1

    # -------------------------------------------------------------
    # 10. Verifikasi Pagination & Universal Search pada GET /api/v1/reports
    # -------------------------------------------------------------
    list_paginated = await client.get(
        "/api/v1/reports?page=1&page_size=10", headers=mgmt_headers
    )
    assert list_paginated.status_code == 200
    p_data = list_paginated.json()
    assert "items" in p_data
    assert "total" in p_data
    assert p_data["page"] == 1
    assert p_data["page_size"] == 10
    assert p_data["total"] >= 1
    assert p_data["total_pages"] >= 1

    # Test universal search pada reports (cari nama freelancer "Budi")
    search_rep = await client.get("/api/v1/reports?q=Budi", headers=mgmt_headers)
    assert search_rep.status_code == 200
    assert search_rep.json()["total"] >= 1

    # -------------------------------------------------------------
    # 11. Verifikasi Pagination & Universal Search pada Produk
    # -------------------------------------------------------------
    prod_search = await client.get(
        "/api/v1/products?q=aren&page=1&page_size=5", headers=free_headers
    )
    assert prod_search.status_code == 200
    ps_data = prod_search.json()
    assert "items" in ps_data
    assert ps_data["total"] >= 1
    assert "Aren" in ps_data["items"][0]["name"]

    # -------------------------------------------------------------
    # 12. Verifikasi Pagination & Universal Search pada Users (Khusus Manajemen)
    # -------------------------------------------------------------
    users_search = await client.get(
        "/api/v1/auth/users?q=Budi&page=1&page_size=10", headers=mgmt_headers
    )
    assert users_search.status_code == 200
    us_data = users_search.json()
    assert "items" in us_data
    assert us_data["total"] >= 1
    assert us_data["items"][0]["name"] == "Freelancer Budi"
