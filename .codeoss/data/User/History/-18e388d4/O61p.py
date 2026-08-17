import os
import base64
import tempfile
import subprocess

from flask import Flask, request, jsonify


app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

INTERNAL_TOKEN = os.environ.get(
    "INTERNAL_TOKEN",
    ""
)


MAX_PDF_SIZE = 20 * 1024 * 1024


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def health():

    return jsonify({
        "status": "ok",
        "service": "pdf-unlocker"
    })


# ============================================================
# UNLOCK PDF
# ============================================================

@app.post("/unlock")
def unlock_pdf():

    # --------------------------------------------------------
    # ตรวจ Token
    # --------------------------------------------------------

    request_token = request.headers.get(
        "X-Internal-Token",
        ""
    )


    if (
        not INTERNAL_TOKEN or
        request_token != INTERNAL_TOKEN
    ):

        return jsonify({
            "error": "Unauthorized"
        }), 401


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify({
            "error": "Invalid JSON"
        }), 400


    pdf_base64 = data.get(
        "pdf_base64"
    )


    password = data.get(
        "password"
    )


    if not pdf_base64:

        return jsonify({
            "error": "Missing pdf_base64"
        }), 400


    if password is None:

        return jsonify({
            "error": "Missing password"
        }), 400


    password = str(password)


    # --------------------------------------------------------
    # Decode PDF
    # --------------------------------------------------------

    try:

        pdf_bytes = base64.b64decode(
            pdf_base64,
            validate=True
        )

    except Exception:

        return jsonify({
            "error": "Invalid PDF Base64"
        }), 400


    # --------------------------------------------------------
    # Size Limit
    # --------------------------------------------------------

    if len(pdf_bytes) > MAX_PDF_SIZE:

        return jsonify({
            "error":
                "PDF ใหญ่เกิน 20 MB"
        }), 413


    # --------------------------------------------------------
    # Temporary files
    # --------------------------------------------------------

    input_path = None
    output_path = None
    password_path = None


    try:

        # ----------------------------------------------------
        # Input PDF
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
    suffix=".pdf",
    delete=False
) as input_file:

    input_file.write(
        pdf_bytes
    )

    input_path = f"/tmp/{file.filename}"


        # ----------------------------------------------------
        # Password file
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            delete=False
        ) as password_file:

            password_file.write(
                password
            )

            password_file.write(
                "\n"
            )

            password_path =
                password_file.name


        # ----------------------------------------------------
        # Output
        # ----------------------------------------------------

        output_file =
            tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False
            )


        output_path =
            output_file.name


        output_file.close()


        # ----------------------------------------------------
        # qpdf
        # ----------------------------------------------------

        command = [

            "qpdf",

            "--password-file=" +
            password_path,

            "--decrypt",

            input_path,

            output_path

        ]


        result =
            subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )


        # ----------------------------------------------------
        # Check qpdf
        # ----------------------------------------------------

        if result.returncode != 0:

            return jsonify({
                "error":
                    "รหัสผ่านไม่ถูกต้อง หรือ PDF ไม่สามารถถอดรหัสได้"
            }), 422


        # ----------------------------------------------------
        # Read output
        # ----------------------------------------------------

        with open(
            output_path,
            "rb"
        ) as unlocked_file:

            unlocked_bytes =
                unlocked_file.read()


        unlocked_base64 =
            base64.b64encode(
                unlocked_bytes
            ).decode(
                "ascii"
            )


        return jsonify({

            "success":
                True,

            "pdf_base64":
                unlocked_base64

        })


    except subprocess.TimeoutExpired:

        return jsonify({
            "error":
                "qpdf ใช้เวลานานเกินไป"
        }), 504


    except Exception as error:

        print(
            "UNLOCK ERROR:",
            str(error)
        )


        return jsonify({
            "error":
                "เกิดข้อผิดพลาดในการปลดล็อก PDF"
        }), 500


    finally:

        # ----------------------------------------------------
        # ลบไฟล์ชั่วคราว
        # ----------------------------------------------------

        for path in [

            input_path,
            output_path,
            password_path

        ]:

            if path:

                try:

                    os.remove(
                        path
                    )

                except Exception:

                    pass


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    port =
        int(
            os.environ.get(
                "PORT",
                "8080"
            )
        )


    app.run(
        host="0.0.0.0",
        port=port
    )