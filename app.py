import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    abort,
    flash,
)
from models import db, Mahasiswa, Catatan
from forms import MahasiswaForm, CatatanForm

app = Flask(__name__)

# Konfigurasi Keamanan dan Database SQLite
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "si-peringatan-dini-rahasia-super-aman-2026"
)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///siews.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inisialisasi Database
db.init_app(app)


# ==============================================================================
# CUSTOM JINJA FILTERS
# ==============================================================================
@app.template_filter("predikat")
def filter_predikat(nilai_ipk) -> str:
    """Filter Jinja untuk mengonversi angka IPK menjadi predikat akademik."""
    try:
        ipk = float(nilai_ipk)
        if ipk >= 3.51:
            return "Dengan Pujian (Cumlaude)"
        elif ipk >= 3.00:
            return "Sangat Memuaskan"
        elif ipk >= 2.50:
            return "Memuaskan"
        elif ipk >= 2.00:
            return "Cukup"
        else:
            return "Kurang / Butuh Bimbingan"
    except (ValueError, TypeError):
        return "-"


@app.template_filter("persen")
def filter_persen(nilai) -> str:
    """Filter Jinja untuk memformat persentase kehadiran dengan 1 desimal."""
    try:
        val = float(nilai)
        if 0.0 <= val <= 1.0:
            val *= 100
        return f"{val:.1f}%"
    except (ValueError, TypeError):
        return "-"


# ==============================================================================
# ROUTING & CONTROLLERS (SQLAlchemy 2.x Query Style)
# ==============================================================================

# Rute 1: Rute Dasar (/) - Menampilkan total mahasiswa & mahasiswa berisiko
@app.route("/")
def index():
    # Hitung total mahasiswa menggunakan db.func.count
    total_mahasiswa = (
        db.session.scalar(db.select(db.func.count(Mahasiswa.id))) or 0
    )

    # Query mahasiswa berisiko: IPK < 2.50 ATAU Kehadiran < 75%
    stmt_berisiko = (
        db.select(Mahasiswa)
        .where(db.or_(Mahasiswa.ipk < 2.50, Mahasiswa.kehadiran < 75))
        .order_by(Mahasiswa.ipk.asc())
    )
    mahasiswa_berisiko = db.session.execute(stmt_berisiko).scalars().all()
    total_berisiko = len(mahasiswa_berisiko)

    # Ambil daftar prodi unik dari database
    stmt_prodi = db.select(Mahasiswa.prodi).distinct().order_by(Mahasiswa.prodi)
    daftar_prodi = db.session.execute(stmt_prodi).scalars().all()

    return render_template(
        "index.html",
        total_mahasiswa=total_mahasiswa,
        total_berisiko=total_berisiko,
        mahasiswa_berisiko=mahasiswa_berisiko,
        daftar_prodi=daftar_prodi,
    )


# Rute 2: Query String (/mahasiswa?prodi=...)
@app.route("/mahasiswa")
def daftar_mahasiswa():
    prodi_filter = request.args.get("prodi", "").strip()

    stmt = db.select(Mahasiswa)
    if prodi_filter:
        stmt = stmt.where(Mahasiswa.prodi.ilike(f"%{prodi_filter}%"))
    stmt = stmt.order_by(Mahasiswa.nim.asc())

    daftar = db.session.execute(stmt).scalars().all()

    stmt_prodi = db.select(Mahasiswa.prodi).distinct().order_by(Mahasiswa.prodi)
    daftar_prodi = db.session.execute(stmt_prodi).scalars().all()

    return render_template(
        "mahasiswa.html",
        daftar_mahasiswa=daftar,
        prodi_aktif=prodi_filter,
        daftar_prodi=daftar_prodi,
    )


# Rute 3: Tambah Mahasiswa Baru (/mahasiswa/tambah - GET & POST)
@app.route("/mahasiswa/tambah", methods=["GET", "POST"])
def tambah_mahasiswa():
    form = MahasiswaForm()

    if form.validate_on_submit():
        mahasiswa = Mahasiswa(
            nim=form.nim.data.strip(),
            nama=form.nama.data.strip(),
            prodi=form.prodi.data,
            ipk=form.ipk.data,
            kehadiran=form.kehadiran.data,
            email=form.email.data.strip() if form.email.data else None,
        )
        db.session.add(mahasiswa)
        db.session.commit()
        flash(
            f"Mahasiswa {mahasiswa.nama} ({mahasiswa.nim}) berhasil ditambahkan ke sistem!",
            "success",
        )
        return redirect(url_for("detail_mahasiswa", nim=mahasiswa.nim))

    # Jika pengiriman POST gagal validasi, kembalikan dengan status kode 422
    if request.method == "POST":
        return render_template("tambah.html", form=form), 422

    return render_template("tambah.html", form=form)


# Rute 4: Detail Mahasiswa & Tambah Catatan (/mahasiswa/<nim> - GET & POST)
@app.route("/mahasiswa/<nim>", methods=["GET", "POST"])
def detail_mahasiswa(nim):
    # Query mahasiswa berdasarkan NIM gaya SQLAlchemy 2.x
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))

    if not mahasiswa:
        abort(404)

    form = CatatanForm()

    # Penanganan penambahan catatan konseling
    if form.validate_on_submit():
        catatan = Catatan(
            mahasiswa_id=mahasiswa.id,
            jenis=form.jenis.data,
            isi=form.isi.data.strip(),
        )
        db.session.add(catatan)
        db.session.commit()
        flash("Catatan konseling baru berhasil disimpan!", "success")
        return redirect(url_for("detail_mahasiswa", nim=mahasiswa.nim))

    return render_template(
        "detail.html",
        mahasiswa=mahasiswa,
        form=form,
        is_berisiko=mahasiswa.is_berisiko,
    )


# Rute 5: Hapus Mahasiswa (/mahasiswa/<nim>/hapus - POST Only)
@app.route("/mahasiswa/<nim>/hapus", methods=["POST"])
def hapus_mahasiswa(nim):
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))

    if not mahasiswa:
        abort(404)

    nama_mhs = mahasiswa.nama
    nim_mhs = mahasiswa.nim

    # Catatan terkait akan otomatis terhapus berkat cascade='all, delete-orphan'
    db.session.delete(mahasiswa)
    db.session.commit()
    flash(
        f"Data mahasiswa {nama_mhs} ({nim_mhs}) beserta catatan terkait telah berhasil dihapus.",
        "warning",
    )
    return redirect(url_for("daftar_mahasiswa"))


# Rute 6: Form Pencarian (/cari) dengan Pola PRG
@app.route("/cari", methods=["GET", "POST"])
def cari():
    if request.method == "POST":
        tipe_pencarian = request.form.get("tipe", "prodi")
        kata_kunci = request.form.get("keyword", "").strip()

        if tipe_pencarian == "nim" and kata_kunci:
            return redirect(url_for("detail_mahasiswa", nim=kata_kunci))
        else:
            return redirect(url_for("daftar_mahasiswa", prodi=kata_kunci))

    stmt_prodi = db.select(Mahasiswa.prodi).distinct().order_by(Mahasiswa.prodi)
    daftar_prodi = db.session.execute(stmt_prodi).scalars().all()
    return render_template("cari.html", daftar_prodi=daftar_prodi)


# Rute 7: Endpoint JSON (/api/mahasiswa/<nim>)
@app.route("/api/mahasiswa/<nim>")
def api_mahasiswa(nim):
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))

    if not mahasiswa:
        return (
            jsonify(
                {
                    "status": "error",
                    "kode": 404,
                    "pesan": f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.",
                }
            ),
            404,
        )

    daftar_catatan = [
        {
            "id": c.id,
            "jenis": c.jenis,
            "isi": c.isi,
            "dibuat": c.dibuat.isoformat() if c.dibuat else None,
        }
        for c in mahasiswa.catatan
    ]

    return jsonify(
        {
            "status": "success",
            "kode": 200,
            "data": {
                "id": mahasiswa.id,
                "nim": mahasiswa.nim,
                "nama": mahasiswa.nama,
                "prodi": mahasiswa.prodi,
                "ipk": mahasiswa.ipk,
                "predikat": filter_predikat(mahasiswa.ipk),
                "kehadiran": filter_persen(mahasiswa.kehadiran),
                "email": mahasiswa.email,
                "is_berisiko": mahasiswa.is_berisiko,
                "total_catatan": len(daftar_catatan),
                "catatan": daftar_catatan,
            },
        }
    )


# ==============================================================================
# PENANGANAN ERROR 404
# ==============================================================================
@app.errorhandler(404)
def penanganan_404(error):
    if request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "status": "error",
                    "kode": 404,
                    "pesan": "Endpoint atau data API tidak ditemukan.",
                }
            ),
            404,
        )
    return render_template("404.html", error=error), 404


# ==============================================================================
# CLI COMMAND: FLASK SEED
# ==============================================================================
@app.cli.command("seed")
def seed():
    """CLI Command untuk reset tabel dan mengisi 5 data dummy mahasiswa & catatan."""
    db.drop_all()
    db.create_all()

    data_dummy = [
        Mahasiswa(
            nim="A11.2023.00001",
            nama="Ahmad Fauzi",
            prodi="SI",
            ipk=3.75,
            kehadiran=92,
            email="ahmad.fauzi@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00002",
            nama="Budi Santoso",
            prodi="TI",
            ipk=2.35,
            kehadiran=68,
            email="budi.santoso@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00003",
            nama="Citra Lestari",
            prodi="SI",
            ipk=3.85,
            kehadiran=96,
            email="citra.lestari@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00004",
            nama="Dewi Anggraini",
            prodi="MI",
            ipk=2.10,
            kehadiran=55,
            email="dewi.anggraini@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00005",
            nama="Eko Prasetyo",
            prodi="TI",
            ipk=3.15,
            kehadiran=81,
            email="eko.prasetyo@kampus.ac.id",
        ),
    ]

    db.session.add_all(data_dummy)
    db.session.flush()  # Dapatkan ID mahasiswa sebelum membuat catatan

    # Catatan konseling dummy untuk mendemonstrasikan relasi One-to-Many
    catatan_budi = Catatan(
        mahasiswa_id=data_dummy[1].id,
        jenis="Akademik",
        isi="Diberikan peringatan dini akademik terkait kehadiran 68% dan IPK 2.35. Dijadwalkan bimbingan intensif pekan depan.",
    )
    catatan_dewi = Catatan(
        mahasiswa_id=data_dummy[3].id,
        jenis="Pribadi",
        isi="Mahasiswa mengalami kendala transportasi sehingga sering terlambat kuliah. Direkomendasikan bantuan asrama.",
    )
    db.session.add_all([catatan_budi, catatan_dewi])
    db.session.commit()

    print("SUCCESS: Database SQLite berhasil di-reset dan diisi 5 data dummy mahasiswa!")


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    app.run(debug=True)
