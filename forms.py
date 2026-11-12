from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    FloatField,
    IntegerField,
    SelectField,
    TextAreaField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    Regexp,
    AnyOf,
    NumberRange,
    Optional,
    Email,
    NoneOf,
    ValidationError,
)
from models import db, Mahasiswa


# ==============================================================================
# 1. FORMULIR MAHASISWA (MahasiswaForm)
# ==============================================================================
class MahasiswaForm(FlaskForm):
    """Formulir input data mahasiswa dengan validasi ketat di sisi server."""

    # NIM: format A11.2023.00001 (1 huruf besar, 2 angka, titik, 4 angka, titik, 5 angka)
    nim = StringField(
        "NIM (Nomor Induk Mahasiswa)",
        validators=[
            DataRequired(message="NIM wajib diisi."),
            Regexp(
                regex=r"^[A-Z]\d{2}\.\d{4}\.\d{5}$",
                message="Format NIM tidak valid! Gunakan format seperti: A11.2023.00001",
            ),
        ],
    )

    nama = StringField(
        "Nama Lengkap",
        validators=[
            DataRequired(message="Nama lengkap wajib diisi."),
            Length(
                min=3,
                max=100,
                message="Nama harus memiliki panjang antara 3 hingga 100 karakter.",
            ),
        ],
    )

    # Prodi: Harus salah satu dari SI, TI, atau MI
    prodi = SelectField(
        "Program Studi",
        choices=[
            ("", "-- Pilih Program Studi --"),
            ("SI", "Sistem Informasi (SI)"),
            ("TI", "Teknologi Informasi (TI)"),
            ("MI", "Manajemen Informatika (MI)"),
        ],
        validators=[
            DataRequired(message="Silakan pilih program studi."),
            AnyOf(
                values=["SI", "TI", "MI"],
                message="Program studi harus salah satu dari: SI, TI, atau MI.",
            ),
        ],
    )

    # Catatan Teknis: Menggunakan InputRequired (bukan DataRequired) agar nilai 0 / 0.0 dianggap valid (sah)
    ipk = FloatField(
        "Indeks Prestasi Kumulatif (IPK)",
        validators=[
            InputRequired(message="IPK wajib diisi."),
            NumberRange(
                min=0.0,
                max=4.0,
                message="IPK harus berada dalam rentang 0.00 hingga 4.00.",
            ),
        ],
    )

    kehadiran = IntegerField(
        "Persentase Kehadiran (%)",
        validators=[
            InputRequired(message="Persentase kehadiran wajib diisi."),
            NumberRange(
                min=0,
                max=100,
                message="Kehadiran harus berada dalam rentang 0 hingga 100%.",
            ),
        ],
    )

    email = StringField(
        "Alamat Email (Opsional)",
        validators=[
            Optional(),
            Email(message="Format alamat email tidak valid."),
        ],
    )

    submit = SubmitField("Simpan Mahasiswa")

    def validate_nim(self, field):
        """Validator khusus untuk memastikan NIM belum pernah terdaftar di basis data."""
        # Query menggunakan standar SQLAlchemy 2.x
        mahasiswa_ada = db.session.scalar(
            db.select(Mahasiswa).filter_by(nim=field.data.strip())
        )
        if mahasiswa_ada:
            raise ValidationError(
                f"NIM '{field.data}' sudah terdaftar dalam sistem. Silakan gunakan NIM lain."
            )


# ==============================================================================
# 2. FORMULIR CATATAN (CatatanForm)
# ==============================================================================
class CatatanForm(FlaskForm):
    """Formulir pencatatan konseling/bimbingan akademik mahasiswa."""

    jenis = SelectField(
        "Jenis Catatan",
        choices=[
            ("Akademik", "Akademik"),
            ("Keuangan", "Keuangan"),
            ("Pribadi", "Pribadi"),
        ],
        validators=[
            DataRequired(message="Silakan pilih jenis catatan."),
        ],
    )

    # Menolak isian bernilai 'tes', 'test', atau '-'
    isi = TextAreaField(
        "Isi Catatan Konseling",
        validators=[
            DataRequired(message="Isi catatan wajib diisi."),
            Length(
                min=10,
                max=500,
                message="Isi catatan harus memiliki panjang antara 10 hingga 500 karakter.",
            ),
            NoneOf(
                values=["tes", "test", "-"],
                message="Isi catatan tidak valid. Dilarang memasukkan teks placeholder seperti 'tes', 'test', atau '-'.",
            ),
        ],
    )

    submit = SubmitField("Simpan Catatan")
