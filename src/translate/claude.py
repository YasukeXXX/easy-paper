import anthropic
from pypdf import PdfReader

client = anthropic.Anthropic()


def check_is_reference(text: str, model: str = "claude-3-sonnet-20240229") -> bool:
    request_text = f'<paper>\n{text}\n</paper>'
    message = client.messages.create(
        model=model,
        max_tokens=1000,
        temperature=0,
        system="入力する論文の断片に参考文献セクションが含まれているかどうかと、本文が含まれているかどうかを判定してください。\n出力形式:\n<contains-body>{true or false}</contains-body>\n<contains-reference>{true or false}</contains-reference>",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": request_text,
                    }
                ]
            }
        ]
    )
    contains_body = extract_tag_bool(message.content[0].text, 'contains-body', default=True)
    contains_reference = extract_tag_bool(message.content[0].text, 'contains-reference', default=False)
    return {
            'contains_body': contains_body,
            'contains_reference': contains_reference,
        }

def extract_tag_bool(text: str, tag: str, default: bool = False) -> bool:
    contents = extract_tag(text, tag)
    if len(contents) == 0:
        return default 
    return any([c in ('True', 'true', 'TRUE') for c in contents])

def parse_reference(text: str, model: str = "claude-3-sonnet-20240229") -> str:
    request_text = f'<paper>\n{text}\n</paper>'
    message = client.messages.create(
        model=model,
        max_tokens=4000,
        temperature=0,
        system="論文の断片に含まれる参考文献の内容全てに対して、 arxiv のものはマークダウン形式のリンクをつけてそうでないものはそのまま、さらに末尾に ^ref{文献番号} (中括弧は不要)をつけて番号付きリスト形式で出力してください。\n出力は<output></output> で囲んでください。\n\n#出力例\n<output>\n31. Sun, Y., Wang, S., Li, Y., Feng, S., Tian, H., Wu, H., Wang, H.: ERNIE 2.0: A continual pre-training framework for language understanding. [arXiv:1907.12412](https://arxiv.org/abs/1907.12412) (2019) ^ref31\n\n32. Sun, Z., Harit, A., Cristea, A.I., Yu, J., Shi, L., Al Moubayed, N.: Contrastive learning with heterogeneous graph attention networks on short text classification. In: IJCNN 2022, pp. 1–6. (2022) ^ref32\n\n33. Tunstall, L., von Werra, L., Wolf, T.: Natural language processing with Transformers. O'Reilly Media, Inc. (2022) ^ref33\n\n...\n</output>",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": request_text,
                    }
                ]
            }
        ]
    )
    outputs = extract_tag(message.content[0].text, 'output')
    return ''.join(outputs)

def _translate_by_claude(text: str, model: str = "claude-3-5-sonnet-20240620", prev_text: str | None = None):
    previous = '' if prev_text else f'<previous>\n{prev_text}\n</previous>\n\n'
    request_text = f'''
{previous}<paper>
{text}
</paper>
    '''
    message = client.messages.create(
        model=model,
        max_tokens=8192,
        temperature=0,
        system="ユーザーは英語を読めないため、<paper>内の論文をマークダウン形式で全文翻訳する必要があります。参考文献セクションは省略し、数式は tex 形式で $ で囲む必要があります。マークダウンのheading は目次の階層構造と対応させてください。\n\nここまでの入力で読み取れる範囲の目次の階層構造を <outline></outline> 内に出力し、翻訳文は <translate></translate> で囲んでください。",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": request_text,
                    }
                ]
            }
        ],
        extra_headers={
            "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"
        }
    )
    return message

def extract_tag(text: str, tag: str):
    import re
    pattern = fr'<{tag}>(.*?)(?:</{tag}>|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    return matches

def dict_to_xml(d: dict) -> str:
    result = []
    for key, value in d.items():
        if value is None:
            continue
        if isinstance(value, dict):
            result.append(f"<{key}>{dict_to_xml(value)}</{key}>")
        else:
            result.append(f"<{key}>{value}</{key}>")
    return "".join(result)

def translate_by_claude(text: str, model: str = "claude-3-5-sonnet-20240620", prev_text: str | None = None):
    message = _translate_by_claude(text, model, prev_text)
    outputs = extract_tag(message.content[0].text, 'translate')
    outline = extract_tag(message.content[0].text, 'outline')
    return {
            'translate': ''.join(outputs),
            'outline': ''.join(outline),
        }

def parse_or_translate(text: str, prev_text: str | None = None):
    content_types = check_is_reference(text, model='claude-3-5-sonnet-20240620')
    outputs = { 'translate': '', 'outline': None }
    if content_types['contains_body']:
        print('\t\ttranslating...')
        tmp = translate_by_claude(text, prev_text=prev_text)
        outputs['translate'] += tmp['translate']
        outputs['outline'] = tmp['outline']
    if content_types['contains_reference']:
        print('\t\tparsing references...')
        reference = parse_reference(text)
        outputs['translate'] += reference
    return outputs

def create_pdf_chunks(pdf_file: str, pages_per_chunk: int = 2, page_limit: int | None = None):
    reader = PdfReader(pdf_file)
    for i in range(0, len(reader.pages[:page_limit]), pages_per_chunk):
        yield ''.join([page.extract_text() for page in reader.pages[i:i+pages_per_chunk]])

def translate_pdf(pdf_file: str, page_limit: int | None = None, cache_dir: str | None = None) -> list[str]:
    from joblib import Memory
    memory = Memory(cache_dir, verbose=0)

    outputs = []
    prev_text = None
    for chunk_idx, chunk in enumerate(create_pdf_chunks(pdf_file, page_limit=page_limit)):
        print(f'\tchunk={chunk_idx}')
        output = memory.cache(parse_or_translate)(chunk, prev_text=prev_text)
        prev_dict = {
                'outline': output['outline'],
                'last_input': '\n'.join([o for o in chunk.split('\n') if o != ''][-3:]),
                'last_output': '\n'.join([o for o in output['translate'].split('\n') if o != ''][-3:]),
                }
        prev_text = dict_to_xml(prev_dict)
        outputs.append(output['translate'])
    return outputs

