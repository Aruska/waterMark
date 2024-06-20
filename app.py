from flask import Flask, render_template, request, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from PIL import Image, ExifTags
import os
import io
import warnings
import zipfile
import urllib.parse

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Pillow 설정 조정
Image.MAX_IMAGE_PIXELS = None
warnings.simplefilter('error', Image.DecompressionBombWarning)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def add_watermark_to_image(image, watermark_image, watermark_percentage):
    try:
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = dict(image._getexif().items())

            if exif[orientation] == 3:
                image = image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image = image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image = image.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            pass

        width, height = image.size
        new_size = max(width, height)
        new_image = Image.new("RGB", (new_size, new_size), color=(255, 255, 255))
        x_offset = (new_size - width) // 2
        y_offset = (new_size - height) // 2
        new_image.paste(image, (x_offset, y_offset))

        watermark_width = int(new_size * (watermark_percentage / 100.0))
        aspect_ratio = watermark_width / watermark_image.width
        watermark_height = int(watermark_image.height * aspect_ratio)
        watermark = watermark_image.resize((watermark_width, watermark_height), Image.LANCZOS)

        position = ((new_size - watermark.width) // 2, (new_size - watermark.height) // 2)
        new_image.paste(watermark, position, watermark)

        final_size = (3240, 3240)
        final_image = new_image.resize(final_size, Image.LANCZOS)

        return final_image
    except Image.DecompressionBombWarning:
        return None

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        image_files = request.files.getlist('image_files')
        use_default_watermark = 'use_default_watermark' in request.form
        watermark_percentage = int(request.form['watermark_percentage'])

        if not image_files or all(image_file.filename == '' for image_file in image_files):
            return redirect(request.url)

        result_images = []
        result_filenames = []
        for image_file in image_files:
            if image_file and allowed_file(image_file.filename):
                image = Image.open(image_file.stream)
                image_filename = image_file.filename

                if use_default_watermark:
                    static_watermark_filename = 'Eterno_Design_Logo_-_PNG.png'
                    watermark_path = os.path.join(app.root_path, 'static', 'image', static_watermark_filename)
                    watermark_image = Image.open(watermark_path)
                else:
                    watermark_file = request.files.get('watermark_file')
                    if watermark_file and allowed_file(watermark_file.filename):
                        watermark_image = Image.open(watermark_file.stream)
                    else:
                        return redirect(request.url)

                result_image = add_watermark_to_image(image, watermark_image, watermark_percentage)
                if result_image:
                    result_images.append(result_image)
                    result_filenames.append(image_filename)

        if result_images:
            if len(result_images) == 1:
                img_io = io.BytesIO()
                result_images[0].save(img_io, 'JPEG')
                img_io.seek(0)
                response = send_file(img_io, as_attachment=True, download_name=result_filenames[0])
                response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{urllib.parse.quote(result_filenames[0])}"
                return response
            else:
                zip_io = io.BytesIO()
                with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for result_image, result_filename in zip(result_images, result_filenames):
                        img_io = io.BytesIO()
                        result_image.save(img_io, 'JPEG')
                        img_io.seek(0)
                        zipf.writestr(result_filename, img_io.read())
                zip_io.seek(0)
                response = send_file(zip_io, as_attachment=True, download_name='watermarked_images.zip')
                response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{urllib.parse.quote('watermarked_images.zip')}"
                return response

    return render_template('upload.html')

@app.route('/returnToHome', methods=['POST'])
def back_to_home():
    return redirect(url_for('upload_file'))

if __name__ == '__main__':
    app.run(debug=True)
