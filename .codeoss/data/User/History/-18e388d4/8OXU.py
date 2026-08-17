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
    # รับ JSON
    # --------------------------------------------------------

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "Invalid JSON"
        }), 400


    # --------------------------------------------------------
    # รับ PDF Base64
    # --------------------------------------------------------

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
    # Decode Base64 -> PDF
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
    # ตรวจขนาดไฟล์
    # --------------------------------------------------------

    if len(pdf_bytes) > MAX_PDF_SIZE:

        return jsonify({
            "error": "PDF ใหญ่เกิน 20 MB"
        }), 413


    # --------------------------------------------------------
    # Temporary files
    # --------------------------------------------------------

    input_path = None
    output_path = None
    password_path = None


    try:

        # ====================================================
        # INPUT PDF
        # ====================================================

        input_file = tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        )

        input_path = input_file.name

        input_file.write(
            pdf_bytes
        )

        input_file.close()


        # ====================================================
        # PASSWORD FILE
        # ====================================================

        password_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            delete=False
        )

        password_path = password_file.name

        password_file.write(
            password
        )

        password_file.write(
            "\n"
        )

        password_file.close()


        # ====================================================
        # OUTPUT PDF
        # ====================================================

        output_file = tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        )

        output_path = output_file.name

        output_file.close()


        # ====================================================
        # QPDF COMMAND
        # ====================================================

        command = [
            "qpdf",

            "--password-file=" + password_path,

            "--decrypt",

            input_path,

            output_path
        ]


        print(
            "Running qpdf..."
        )


        # ====================================================
        # RUN QPDF
        # ====================================================

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120
        )


        print(
            "qpdf return code:",
            result.returncode
        )


        # ====================================================
        # QPDF ERROR
        # ====================================================

        if result.returncode != 0:

            print(
                "qpdf stderr:",
                result.stderr
            )

            return jsonify({

                "success": False,

                "error":
                    "รหัสผ่านไม่ถูกต้อง หรือ PDF ไม่สามารถถอดรหัสได้"

            }), 422


        # ====================================================
        # READ UNLOCKED PDF
        # ====================================================

        with open(
            output_path,
            "rb"
        ) as unlocked_file:

            unlocked_bytes = (
                unlocked_file.read()
            )


        # ====================================================
        # PDF -> BASE64
        # ====================================================

        unlocked_base64 = (
            base64.b64encode(
                unlocked_bytes
            ).decode("ascii")
        )


        # ====================================================
        # RESPONSE
        # ====================================================

        return jsonify({

            "success": True,

            "pdf_base64":
                unlocked_base64,

            "size":
                len(unlocked_bytes)

        })


    # ========================================================
    # TIMEOUT
    # ========================================================

    except subprocess.TimeoutExpired:

        return jsonify({

            "success": False,

            "error":
                "qpdf ใช้เวลานานเกินไป"

        }), 504


    # ========================================================
    # GENERAL ERROR
    # ========================================================

    except Exception as error:

        print(
            "UNLOCK ERROR:",
            str(error)
        )

        return jsonify({

            "success": False,

            "error":
                "เกิดข้อผิดพลาดในการปลดล็อก PDF"

        }), 500


    # ========================================================
    # CLEANUP
    # ========================================================

    finally:

        for path in [
            input_path,
            output_path,
            password_path
        ]:

            if path:

                try:

                    if os.path.exists(path):

                        os.remove(path)

                except Exception as cleanup_error:

                    print(
                        "Cleanup error:",
                        cleanup_error
                    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "8080"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )