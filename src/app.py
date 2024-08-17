import os
import argparse
import src.notion as notion
from src.translate import gemini, claude

@notion.db(os.environ["NOTION_REFERENCE_DB"])
class Reference:
    pass

def has_extension(filename: str) -> bool:
    import re
    pattern = r'\.(pdf|png|txt|jpg|jpeg)$'
    return bool(re.search(pattern, filename))

def download_from_url(url: str, save_dir: str = '.'):
    import os
    import requests
    import mimetypes

    os.makedirs(save_dir, exist_ok=True)
    filename = os.path.basename(url)
    save_path = os.path.join(save_dir, filename)
    response = requests.get(url)
    if not has_extension(filename):
        content_type = response.headers.get('Content-Type')
        extension = mimetypes.guess_extension(content_type)
        save_path += extension
    with open(save_path, 'wb') as file:
        file.write(response.content)
    return save_path

def get_repository(repo: str, token: str):
    from github import Github
    gh = Github(token)
    repo = gh.get_repo(repo)
    return repo

def extract_title(page: dict) -> str:
    titles = next(( prop for prop in page['properties'].values() if prop['id'] == 'title'))['title']
    return ''.join([title['plain_text'] for title in titles])

def title_to_filename(text: str) -> str:
    import re
    pattern = r'\[[\d\.]+\]'
    result = re.sub(pattern, '', text)

    invalid_chars = r'[<>:"/\\|*\x00-\x1F]'
    result = re.sub(invalid_chars, '', result)
    return result.strip()


def generate_obsidian_template(additional_prop: dict | None = None):
    import datetime
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now(ZoneInfo('Asia/Tokyo'))

    creation_date_x = int(now.timestamp()*1000)
    creation_date = now.strftime("%Y-%m-%dT%H:%M:%S")

    additionals = ''
    if additional_prop is not None:
        additionals = '\n' + '\n'.join([f'{key}: {val}' for key, val in additional_prop.items()])

    template = f"""---
id: {creation_date_x}
aliases: 
tags: 
  - paper
created: {creation_date}
updated: {creation_date}{additionals}
---

"""
    return template

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Translate and format arxiv papers')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--github_repository', type=str)
    parser.add_argument('--github_path', type=str, default='')
    parser.add_argument('--github_branch', type=str, default='main')
    parser.add_argument('--llm', type=str, default='gemini')
    args = parser.parse_args()

    repository = None
    if args.github_repository is not None:
        repository = get_repository(args.github_repository, os.environ['GITHUB_TOKEN'])

    res = Reference.query(
            filter={ 'and': [
                { 'property': 'Created', 'date': { 'after': '2024-07-19'}},
                { 'property': 'Translate Status', 'status': { 'equals': 'Not started'}},
                { 'property': 'URL', "rich_text": { "contains": "arxiv.org/abs" }},
                ]},
            sorts=[{ "property": "Created", "direction": "ascending" }],
            iterate=True,
        )

    for page_idx, page in enumerate(res):
        if args.limit is not None and page_idx >= args.limit:
            break
        url = page['properties']['URL']['url'].replace('abs', 'pdf')
        print(f'Start translation: {url}')
        path = download_from_url(url, save_dir='tmp')
        if args.llm == 'claude':
            texts = claude.translate_pdf(path, cache_dir='tmp/cache')
        else:
            texts = gemini.translate_pdf(path, cache_dir='tmp/cache')

        with open(path+'.md', 'w') as f:
            f.write(''.join(texts))

        if repository is not None:
            filename = title_to_filename(extract_title(page))+'.md'
            md_property = generate_obsidian_template({ 'url': url })
            content = md_property + ''.join(texts)
            repository.create_file(
                    path=os.path.join(args.github_path, filename),
                    message=f'Add {filename}',
                    content=content,
                    branch=args.github_branch,
                )

        for text in texts:
            paragraphs = text.split('\n')
            size = 30
            for i in range(0, len(paragraphs), size):
                notion.append_text_block(page['id'], paragraphs[i:i+size])
        notion.NOTION_CLIENT.pages.update(page_id=page['id'], properties={ 'Translate Status': { 'status': { 'name': 'Done' } } })


