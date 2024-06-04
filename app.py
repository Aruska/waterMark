from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from PIL import Image, ExifTags
import os

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def add_watermark_to_image(image_path, watermark_image_path, output_path, watermark_percentage):
    image = Image.open(image_path)
    watermark = Image.open(watermark_image_path)

    # 이미지의 EXIF 태그에서 방향 정보 가져오기
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = dict(image._getexif().items())

        # 이미지의 방향에 따라 이미지 회전
        if exif[orientation] == 3:
            image = image.rotate(180, expand=True)
        elif exif[orientation] == 6:
            image = image.rotate(270, expand=True)
        elif exif[orientation] == 8:
            image = image.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError):
        # EXIF 정보가 없는 경우, 이미지를 그대로 유지
        pass

    # 이미지의 크기 가져오기
    width, height = image.size

    # 더 큰 쪽을 기준으로 정사각형 크기 계산
    new_size = max(width, height)

    # 새로운 이미지 생성
    new_image = Image.new("RGB", (new_size, new_size), color=(255, 255, 255))

    # 원본 이미지를 새로운 이미지의 중앙에 붙여넣기
    x_offset = (new_size - width) // 2
    y_offset = (new_size - height) // 2
    new_image.paste(image, (x_offset, y_offset))

    # 워터마크 이미지 크기 조정
    watermark_width = int(new_size * (watermark_percentage / 100.0))
    aspect_ratio = watermark_width / watermark.width
    watermark_height = int(watermark.height * aspect_ratio)
    watermark = watermark.resize((watermark_width, watermark_height), Image.LANCZOS)

    # 워터마크 이미지를 중앙에 배치
    position = ((new_size - watermark.width) // 2, (new_size - watermark.height) // 2)
    new_image.paste(watermark, position, watermark)

    # 결과 이미지 저장
    result_filename = os.path.splitext(os.path.basename(image_path))[0] + '_wm.jpg'
    result_path = os.path.join(os.path.dirname(image_path), result_filename)
    new_image.save(result_path, format='JPEG')

    return result_filename


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        image_files = request.files.getlist('image_files')
        use_default_watermark = 'use_default_watermark' in request.form
        watermark_percentage = int(request.form['watermark_percentage'])

        if not image_files or all(image_file.filename == '' for image_file in image_files):
            return redirect(request.url)

        result_filenames = []
        for image_file in image_files:
            if image_file and allowed_file(image_file.filename):
                image_filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                image_file.save(image_path)

                # 체크박스 상태에 따라 워터마크 경로 설정
                if use_default_watermark:
                    # 고정된 워터마크 이미지 경로 사용
                    static_watermark_filename = 'Eterno_Design_Logo_-_PNG.png'
                    watermark_path = os.path.join(app.root_path, 'static', 'image', static_watermark_filename)
                else:
                    # 업로드 워터마크 이미지 사용
                    watermark_file = request.files.get('watermark_file')
                    if watermark_file and allowed_file(watermark_file.filename):
                        watermark_filename = secure_filename(watermark_file.filename)
                        watermark_path = os.path.join(app.config['UPLOAD_FOLDER'], watermark_filename)
                        watermark_file.save(watermark_path)
                    else:
                        return redirect(request.url)

                result_filename = add_watermark_to_image(image_path, watermark_path, image_path, watermark_percentage)
                result_filenames.append(result_filename)

                # 업로드된 이미지와 워터마크 이미지 삭제
                os.remove(image_path)
                if not use_default_watermark and 'watermark_file' in locals():
                    os.remove(watermark_path)

        return redirect(url_for('uploaded_files', filenames=','.join(result_filenames)))

    return render_template('upload.html')


@app.route('/uploads')
def uploaded_files():
    filenames = request.args.get('filenames').split(',')
    return render_template('uploaded.html', filenames=filenames)


@app.route('/returnToHome', methods=['POST'])
def back_to_home():
    return redirect(url_for('upload_file'))


if __name__ == '__main__':
    app.run(debug=True)
