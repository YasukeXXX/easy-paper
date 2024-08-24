import os
from urllib.parse import urlparse
from . import gemini, claude
from src.utils import download_from_url, get_repository, generate_obsidian_template, to_valid_filename

import argparse

parser = argparse.ArgumentParser(description='Translate and format arxiv papers')
parser.add_argument('path_or_url', type=str)
parser.add_argument('--github_repository', type=str)
parser.add_argument('--github_path', type=str, default='')
parser.add_argument('--github_branch', type=str, default='main')
parser.add_argument('--llm', type=str, default='gemini')
args = parser.parse_args()

path = args.path_or_url
if urlparse(args.path_or_url).scheme in ['http', 'https']:
    path = download_from_url(args.path_or_url, save_dir='tmp')

repository = None
if args.github_repository is not None:
    repository = get_repository(args.github_repository, os.environ['GITHUB_TOKEN'])

if args.llm == 'claude':
    translate = claude.translate_pdf
else:
    translate = gemini.translate_pdf

texts = translate(path, cache_dir='tmp/cache')

with open(path+'.md', 'w') as f:
    f.write(''.join(texts))

title = next((text for text in texts if text != ''))
if repository is not None:
    filename = to_valid_filename(title)+'.md'
    md_property = generate_obsidian_template({ 'url': args.path_or_url })
    content = md_property + ''.join(texts)
    repository.create_file(
            path=os.path.join(args.github_path, filename),
            message=f'Add {filename}',
            content=content,
            branch=args.github_branch,
        )

