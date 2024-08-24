import os
import argparse
import src.notion as notion
from src.translate import gemini, claude
from src.utils import download_from_url, get_repository, generate_obsidian_template, to_valid_filename

@notion.db(os.environ["NOTION_REFERENCE_DB"])
class Reference:
    pass

def extract_title(page: dict) -> str:
    titles = next(( prop for prop in page['properties'].values() if prop['id'] == 'title'))['title']
    return ''.join([title['plain_text'] for title in titles])

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
            filename = to_valid_filename(extract_title(page))+'.md'
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


