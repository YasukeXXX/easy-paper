import os
import argparse

from .app import download_from_url

def extract_and_save_images(pdf_file: str, prefix: str = '.') -> str:
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
    return save_dir

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A simple argparse example')
    parser.add_argument('--arxiv_id', type=str)
    parser.add_argument('--url', type=str)
    args = parser.parse_args()

    url = args.url
    if args.arxiv_id is not None:
        url = f'https://arxiv.org/pdf/{args.arxiv_id}'
    path = download_from_url(url, save_dir='tmp')
    save_dir = extract_and_save_images(path, 'tmp')
    print(f"Save images: {save_dir}/")

