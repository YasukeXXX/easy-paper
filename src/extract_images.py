import os
import argparse

def extract_and_save_images(pdf_file: str, prefix: str = '.') -> list[str]:
    from pypdf import PdfReader

    file_id = os.path.basename(pdf_file.rstrip('.pdf'))
    save_dir = os.path.join(prefix, file_id)
    os.makedirs(save_dir, exist_ok=True)
    reader = PdfReader(pdf_file)
    paths = []
    for page_idx, page in enumerate(reader.pages):
        for image_idx, image in enumerate(page.images):
            name = f'page{str(page_idx).zfill(3)}-image{str(image_idx).zfill(2)}.png'
            path = os.path.join(save_dir, name)
            image.image.save(path)
            paths.append(path)
    return paths

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A simple argparse example')
    parser.add_argument('path', type=str)
    args = parser.parse_args()

    extract_and_save_images(args.path, 'tmp')

