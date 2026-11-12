import os
import unittest

# ==============================================================================
# KONFIGURASI PENGUJIAN ISOLASI (IN-MEMORY DATABASE & NONAKTIFKAN CSRF)
# ==============================================================================
# Konfigurasikan sqlite:// (in-memory) sebelum import agar tidak menyentuh siews.db
os.environ["DATABASE_URL"] = "sqlite://"

from app import app
from models import db, Mahasiswa, Catatan

# Set konfigurasi pengujian
app.config["TESTING"] = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
app.config["WTF_CSRF_ENABLED"] = (
    False  # Nonaktifkan sementara CSRF untuk pengujian payload form
)


class TestSIPeringatanDini(unittest.TestCase):
    """Test suite otomatis menggunakan SQLite in-memory dan Flask test_client()."""

    def setUp(self):
        """Menyiapkan konteks aplikasi dan database in-memory bersih sebelum tiap tes."""
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

        # Buat seluruh tabel skema di memory
        db.create_all()

        # Masukkan 1 data awal untuk pengujian referensi
        self.mhs_awal = Mahasiswa(
            nim="A11.2023.00001",
            nama="Ahmad Fauzi",
            prodi="SI",
            ipk=3.75,
            kehadiran=92,
            email="ahmad.fauzi@kampus.ac.id",
        )
        db.session.add(self.mhs_awal)
        db.session.commit()

    def tearDown(self):
        """Membersihkan sesi dan menghapus database in-memory setelah tiap tes selesai."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================================================
    # SKENARIO 1: Pengiriman Form MahasiswaForm dengan Data Valid (Status 302)
    # ==========================================================================
    def test_post_mahasiswa_valid_status_302(self):
        """Memastikan data form valid berhasil disimpan dan server merespons 302 Redirect."""
        payload = {
            "nim": "A11.2023.00002",
            "nama": "Budi Santoso",
            "prodi": "TI",
            "ipk": 2.35,
            "kehadiran": 68,
            "email": "budi.santoso@kampus.ac.id",
        }

        response = self.client.post("/mahasiswa/tambah", data=payload)

        # 1. Pastikan kembali status 302 (Redirect)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/mahasiswa/A11.2023.00002", response.headers["Location"])

        # 2. Verifikasi data berhasil tersimpan di database via ORM
        mhs = db.session.scalar(
            db.select(Mahasiswa).filter_by(nim="A11.2023.00002")
        )
        self.assertIsNotNone(mhs)
        self.assertEqual(mhs.nama, "Budi Santoso")
        self.assertEqual(mhs.prodi, "TI")
        self.assertEqual(mhs.ipk, 2.35)
        self.assertEqual(mhs.kehadiran, 68)

    # ==========================================================================
    # SKENARIO 2: Pengiriman Form dengan Data Salah Semua (Status 422 & Error Muncul)
    # ==========================================================================
    def test_post_mahasiswa_semua_data_salah_status_422(self):
        """Memastikan pengiriman seluruh data salah mengembalikan 422 dan pesan error validasi."""
        payload_salah = {
            "nim": "format_salah_123",  # Tidak sesuai regex A11.2023.00001
            "nama": "Al",  # Kurang dari panjang minimum (min=3)
            "prodi": "KEDOKTERAN",  # Bukan salah satu dari: SI, TI, MI
            "ipk": 5.5,  # Di luar rentang 0.00 - 4.00
            "kehadiran": 150,  # Di luar rentang 0 - 100
            "email": "bukan-format-email",  # Format email tidak valid
        }

        response = self.client.post("/mahasiswa/tambah", data=payload_salah)

        # 1. Pastikan kembali status 422 (Unprocessable Content)
        self.assertEqual(response.status_code, 422)

        html = response.get_data(as_text=True)

        # 2. Pastikan pesan error spesifik muncul di halaman HTML
        self.assertIn("Format NIM tidak valid", html)
        self.assertIn(
            "Nama harus memiliki panjang antara 3 hingga 100", html
        )
        self.assertIn("Program studi harus salah satu dari: SI, TI, atau MI", html)
        self.assertIn("IPK harus berada dalam rentang", html)
        self.assertIn("Kehadiran harus berada dalam rentang", html)
        self.assertIn("Format alamat email tidak valid", html)

    # ==========================================================================
    # SKENARIO 3: Pengiriman NIM yang Sudah Ada (Validasi Khusus validate_nim)
    # ==========================================================================
    def test_post_mahasiswa_nim_duplikat_tertolak_422(self):
        """Memastikan validator khusus validate_nim menolak NIM yang sudah terdaftar."""
        # NIM A11.2023.00001 sudah didaftarkan di setUp()
        payload_duplikat = {
            "nim": "A11.2023.00001",
            "nama": "Siswa Kembar",
            "prodi": "SI",
            "ipk": 3.20,
            "kehadiran": 85,
            "email": "siswa.kembar@kampus.ac.id",
        }

        response = self.client.post("/mahasiswa/tambah", data=payload_duplikat)

        # 1. Status kode harus 422
        self.assertEqual(response.status_code, 422)

        # 2. Pesan error dari metode khusus validate_nim muncul
        html = response.get_data(as_text=True)
        self.assertIn("sudah terdaftar dalam sistem", html)

    # ==========================================================================
    # SKENARIO 4: Uji Relasi ORM (Menambahkan Catatan & Memverifikasi Akses Dua Arah)
    # ==========================================================================
    def test_relasi_mahasiswa_catatan_orm(self):
        """Memastikan penambahan catatan konseling terhubung ke mahasiswa via relasi ORM."""
        payload_catatan = {
            "jenis": "Akademik",
            "isi": "Konseling perencanaan tugas akhir dan evaluasi performa akademik semester.",
        }

        # POST catatan baru ke endpoint detail mahasiswa A11.2023.00001
        response = self.client.post(
            "/mahasiswa/A11.2023.00001", data=payload_catatan
        )
        self.assertEqual(response.status_code, 302)

        # Verifikasi relasi lewat query ORM (Mahasiswa -> Catatan)
        mahasiswa = db.session.scalar(
            db.select(Mahasiswa).filter_by(nim="A11.2023.00001")
        )
        self.assertEqual(len(mahasiswa.catatan), 1)

        catatan = mahasiswa.catatan[0]
        self.assertEqual(catatan.jenis, "Akademik")
        self.assertEqual(
            catatan.isi,
            "Konseling perencanaan tugas akhir dan evaluasi performa akademik semester.",
        )

        # Verifikasi akses relasi dua arah (Catatan -> Mahasiswa via back_populates)
        self.assertEqual(catatan.mahasiswa.nim, "A11.2023.00001")
        self.assertEqual(catatan.mahasiswa.nama, "Ahmad Fauzi")

    # ==========================================================================
    # SKENARIO PENDUKUNG: Pengujian Rute Dasar, Filter Prodi, dan API JSON
    # ==========================================================================
    def test_get_rute_dasar_dan_filter_prodi(self):
        """Memastikan rute / dan /mahasiswa?prodi= berjalan normal."""
        resp_index = self.client.get("/")
        self.assertEqual(resp_index.status_code, 200)

        resp_prodi = self.client.get("/mahasiswa?prodi=SI")
        self.assertEqual(resp_prodi.status_code, 200)
        self.assertIn("Ahmad Fauzi", resp_prodi.get_data(as_text=True))

    def test_api_json_respons(self):
        """Memastikan API JSON mengembalikan data mahasiswa dan list catatan."""
        response = self.client.get("/api/mahasiswa/A11.2023.00001")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)

        data = response.get_json()["data"]
        self.assertEqual(data["nim"], "A11.2023.00001")
        self.assertEqual(data["predikat"], "Dengan Pujian (Cumlaude)")
        self.assertEqual(data["kehadiran"], "92.0%")


if __name__ == "__main__":
    unittest.main(verbosity=2)
