# Backend - Arloraka Coffee (Monitoring Kontribusi Penjualan Freelancer)

REST API backend untuk mencatat, memverifikasi, dan memantau kontribusi penjualan freelancer Arloraka Coffee.

- **Tim Capstone:** A26-CS147
- **Stack:** FastAPI (Python) + PostgreSQL (Supabase) + SQLAlchemy 2.0 (Async) + Pydantic V2
- **Status Fitur:**
  - ✅ **Autentikasi & RBAC:** JWT Token untuk peran `management` dan `freelancer`.
  - ✅ **Master Produk:** CRUD produk kopi dengan pagination dan pencarian universal (`q`).
  - ✅ **Alur Laporan Penjualan:** Submit laporan, auto-hitung omzet & komisi 10% (pembulatan ke atas), upload bukti gambar/file.
  - ✅ **Alur Verifikasi:** Manajemen Approve, Reject, atau Minta Revisi (wajib alasan).
  - ✅ **Alur Revisi:** Freelancer kirim perbaikan dengan **ID laporan yang sama** (anti duplikasi).
  - ✅ **Universal Search & Pagination:** Pada semua endpoint inquiry laporan, produk, dan users.
  - ✅ **Seeder Database:** Script impor otomatis 6 master produk, 10 akun freelancer, dan 750 transaksi dummy (sinkron 0% selisih dengan acuan tim DS).

---

## 1. Prasyarat Sistem

- Python 3.12+ (direkomendasikan Python 3.12 - 3.14)
- Koneksi Internet (untuk koneksi ke PostgreSQL Cloud Supabase)

---

## 2. Langkah Setup & Instalasi Backend

Jalankan perintah berikut di terminal (PowerShell / Command Prompt / Terminal):

```bash
# 1. Masuk ke folder backend
cd backend

# 2. Buat virtual environment (jika belum ada)
python -m venv .venv

# 3. Aktifkan virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# atau (Command Prompt CMD):
.\.venv\Scripts\activate.bat
# atau (Linux / macOS):
source .venv/bin/activate

# 4. Install seluruh dependensi
pip install -r requirements.txt -r requirements-dev.txt

# 5. Siapkan file konfigurasi environment
copy .env.example .env     # Windows
cp .env.example .env       # Linux/macOS
```

> **Catatan Database:** File `.env` sudah dikonfigurasikan terhubung ke database cloud PostgreSQL di **Supabase**. Pastikan nilai `DATABASE_URL` di file `.env` sudah terisi connection string Supabase.

---

## 3. Database Seeding (Mengisi 750 Data Dummy)

Untuk membuat tabel otomatis di database Supabase dan mengimpor master produk, akun freelancer, serta 750 data transaksi dummy:

```bash
python -m app.db.seed
```

---

## 4. Menjalankan Server Backend

Jalankan server menggunakan modul Uvicorn:

```bash
python -m uvicorn app.main:app --reload
```

Jika berhasil, server akan berjalan di:
- **Base URL:** `http://127.0.0.1:8000`
- **Health Check:** `http://127.0.0.1:8000/health`
- **Swagger Interactive API Docs:** `http://127.0.0.1:8000/docs`

---

## 5. Cara Pengujian API Melalui Browser (Swagger UI)

Pengujian API tidak memerlukan Postman, cukup menggunakan **Swagger UI** bawaan FastAPI yang interaktif di browser.

### A. Buka Halaman Pengujian
Buka browser dan akses URL:
👉 **`http://127.0.0.1:8000/docs`**

---

### B. Langkah Pengujian Langkah-demi-Langkah:

#### Langkah 1: Login untuk Mendapatkan Token JWT
1. Cari endpoint **`POST /api/v1/auth/login`**.
2. Klik tombol **Try it out** di sebelah kanan.
3. Masukkan akun uji coba pada kotak Request body:
   - **Login sebagai Manajemen (Admin):**
     ```json
     {
       "email": "admin@arloraka.com",
       "password": "admin123"
     }
     ```
   - **Login sebagai Freelancer (Contoh: Andi):**
     ```json
     {
       "email": "andi@freelance.arloraka.com",
       "password": "freelancer123"
     }
     ```
4. Klik tombol biru **Execute**.
5. Pada bagian **Server response (200 OK)**, copy nilai string `"access_token"` (tanpa tanda kutip).

---

#### Langkah 2: Memasang Token Autentikasi (Authorize)
1. Scroll ke bagian paling atas halaman Swagger UI.
2. Klik tombol hijau berikon gembok 🔒 **Authorize** di pojok kanan atas.
3. Di kolom isian **Value**, ketikkan format berikut:
   ```text
   Bearer <ACCESS_TOKEN_YANG_TADI_DICOPOY>
   ```
   *(Contoh: `Bearer eyJhbGciOi...`)*
4. Klik tombol **Authorize**, lalu klik **Close**.
5. Sekarang ikon gembok pada endpoint akan terkunci tertutup (menandakan kamu sudah login).

---

#### Langkah 3: Menguji Endpoint Fitur

1. **Cek Daftar Menu Kopi (`GET /api/v1/products`):**
   - Klik **Try it out** $\rightarrow$ **Execute**.
   - Output: 6 varian kopi resmi (Americano Rp 10.000, Aren Latte Rp 16.000, dll).
   - Fitur pencarian: Coba isi kolom `q` dengan kata `"aren"`, lalu Execute.

2. **Cek Laporan Transaksi (`GET /api/v1/reports`):**
   - Klik **Try it out** $\rightarrow$ **Execute**.
   - **Jika login sebagai Admin:** Menampilkan seluruh laporan transaksi (750 data) dengan pagination (`page`, `page_size`).
   - **Jika login sebagai Andi:** Backend secara otomatis hanya menampilkan laporan milik Andi (Role-Based Data Isolation).
   - Fitur pencarian: Coba isi kolom `q` dengan `"TRX-0010"` atau lokasi `"Car Free Day"`.

3. **Freelancer Mengirim Laporan Penjualan (`POST /api/v1/reports`):**
   - Hanya bisa dilakukan jika login sebagai Freelancer.
   - Masukkan ID produk dan kuantitas botol yang terjual. Omzet dan komisi 10% (dibulatkan ke atas) akan dihitung otomatis oleh server.

4. **Upload File Bukti Transaksi (`POST /api/v1/reports/{report_id}/proofs`):**
   - Masukkan `report_id` laporan yang ingin diunggah buktinya.
   - Pilih file foto nota/transfer (format JPG/PNG/PDF), lalu klik Execute.

5. **Manajemen Memverifikasi Laporan (`PATCH /api/v1/reports/{report_id}/verify`):**
   - Hanya bisa dilakukan jika login sebagai Admin.
   - Pilihan status: `approved`, `rejected`, atau `revision` (wajib mengisi `revision_notes`).

---

## 6. Daftar Kredensial Akun Uji Coba (Demo Accounts)

| Peran (Role) | Nama | Email | Password | Hak Akses |
| :--- | :--- | :--- | :--- | :--- |
| **Management** | Admin Arloraka | `admin@arloraka.com` | `admin123` | Akses penuh: kelola produk, verifikasi/revisi laporan, lihat semua data |
| **Freelancer** | Andi | `andi@freelance.arloraka.com` | `freelancer123` | Kirim laporan, upload bukti, revisi laporan sendiri |
| **Freelancer** | Bima | `bima@freelance.arloraka.com` | `freelancer123` | Akun freelancer mitra 2 |
| **Freelancer** | Citra | `citra@freelance.arloraka.com` | `freelancer123` | Akun freelancer mitra 3 |

*(Total ada 10 akun freelancer dummy: Andi, Bima, Citra, Dimas, Eka, Farhan, Gita, Hana, Iqbal, Jihan dengan password sama: `freelancer123`)*

---

## 7. Menjalankan Pengujian Otomatis (Pytest)

Untuk memvalidasi integritas fungsi hitung komisi, alur perbaikan revisi dengan ID yang sama, dan pembatasan peran antarpengguna:

```bash
python -m pytest -v
```
Seluruh 7 skenario pengujian bisnis lulus 100% tanpa error.
