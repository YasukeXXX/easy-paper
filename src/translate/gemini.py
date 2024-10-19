import os
from abc import ABC, abstractmethod
import json
import google.generativeai as genai
from google.generativeai.types import StopCandidateException
from pydantic.dataclasses import dataclass
from pydantic import BaseModel, ValidationError
from string import Template
import time

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

class GeminiModule(ABC):
    model: str
    system_instruction: str
    message: str
    output_type: type[str] | type[BaseModel] = str
    max_retry: int = 3

    def fill_system_instruction(self, inputs: dict[str, str]) -> str:
        template = Template(self.system_instruction)
        if self.json_mode() and hasattr(self.output_type, 'model_json_schema'):
            inputs['json_schema'] = json.dumps(self.output_type.model_json_schema())
        return template.substitute(inputs)

    def fill_message(self, inputs: dict[str, str]) -> str:
        template = Template(self.message)
        return template.substitute(inputs).encode(errors='ignore').decode()

    def json_mode(self) -> bool:
        return self.output_type is not str

    def get_model(self, instruction: str) -> genai.GenerativeModel:
        mime_type = "application/json" if self.json_mode() else "text/plain"
        generation_config = {
          "temperature": 0.5,
          "top_p": 0.95,
          "top_k": 40,
          "max_output_tokens": 8192,
          "response_mime_type": mime_type,
        }
        
        return genai.GenerativeModel(
          model_name=self.model,
          generation_config=generation_config,
          system_instruction=instruction,
        )

    def get_type_exception(self, text: str) -> Exception | None:
        if not self.json_mode():
            return None
        try:
            if not hasattr(self.output_type, 'model_validate_json'):
                json.loads(text)
                return None
            self.output_type.model_validate_json(text)
            return None
        except ValidationError as e:
            return e

    def call_gemini(self, inputs: dict[str, str]) -> genai.types.GenerateContentResponse:
        model = self.get_model(self.fill_system_instruction(inputs))
        chat_session = model.start_chat()
        response = chat_session.send_message(self.fill_message(inputs))

        err = self.get_type_exception(response.text)
        chat_session.model._generation_config['temperature'] = 1
        for i in range(self.max_retry):
            if err is None:
                break
            response = chat_session.send_message("Fix ValidationError: " + str(err))
            err = self.get_type_exception(response.text)
        if err is not None:
            raise err
        return response

    def __call__(self, inputs: dict[str, str]):
        response = self.call_gemini(inputs)
        if self.json_mode() and hasattr(self.output_type, 'model_validate_json'):
            return self.output_type.model_validate_json(response.text)
        return response.text

class Section(BaseModel):
    title: str
    line: int
    sections: list["Section"]
    is_references: bool = False

class StructuredPaper(BaseModel):
    title: str
    keywords: list[str]
    sections: list[Section]

class ExtractOutlineResponse(BaseModel):
    paper: StructuredPaper

class ExtractOutline(GeminiModule):
    model = "gemini-1.5-pro-002"
    output_type = ExtractOutlineResponse
    system_instruction = '''
入力した論文のセクションを構造化してください

出力形式
{
  "paper": {
    "title": str,
    "keywords": list[str],
    "sections": [{ "title": str, "line": number, "is_references": bool, "sections": [{ "title": str, "line": number, "sections": [...]}] }],
  }
}

JSON Schema
${json_schema}
'''
    message = "${full_text}"


class ExtractSingleSection(GeminiModule):
    model = "gemini-1.5-flash"
    output_type = str
    message = "${full_text}"
    system_instruction = 'Extract the entire `${title}` section of the entered paper'


class TranslateSingleSection(GeminiModule):
    model = "gemini-1.5-flash"
    output_type = str
    message = "${full_text}"
    system_instruction = '入力した文章を翻訳してマークダウン形式で出力してください。数式は tex 形式で $$ で囲んでください。'


class ReplaceEquation(GeminiModule):
    model = "gemini-1.5-flash"
    output_type = str
    message = "${full_text}"
    system_instruction = '入力した文章中の数式を tex 形式に変換して $$ で囲んでください。'

class Reference(BaseModel):
    anchor: str | int
    title: str
    link: str | None
    magazine: str | None
    year: int | None

    def __str__(self) -> str:
        year = '' if self.year is None else f'({self.year})'
        if self.link is None:
            return f'1. {self.title} {year} ^ref{self.anchor}'
        return f"1. [{self.title}]({self.link}) {year} ^ref{self.anchor}"

class ConvertReferencesResponse(BaseModel):
    references: list[Reference]

class ConvertReferences(GeminiModule):
    model = "gemini-1.5-flash"
    output_type = ConvertReferencesResponse
    message = "${full_text}"
    system_instruction = '''
参考文献の内容を構造化してください

#出力形式
{
  "references": [
    { "anchor": str | number, "title": str,  "link": str | None, "year": number,  "magazine": str }
  ]
}

JSON Schema
${json_schema}
'''

class TranslatePaper:
    def __init__(self, interval: int = 3):
        self.extract_outline = ExtractOutline()
        self.translate_single_section = TranslateSingleSection()
        self.replace_equation = ReplaceEquation()
        self.convert_references = ConvertReferences()
        self.interval = interval

    def convert_references_source(self, text: str):
        import re
        def replace_reference(match):
            if match.group(1):
                return match.group(0)
            if match.group(2):  # $ で囲まれていない場合
                numbers = match.group(2).strip('[]').split(',')
                return ' '.join(f'[[#^ref{num.strip()}]]' for num in numbers)

        # $ で囲まれた部分を除外し、それ以外の [数字] パターンにマッチする正規表現
        pattern = r'(\$[^\$]*\$)|(\[(\d+(?:,\s*\d+)*)\])'
        return re.sub(pattern, replace_reference, text)

    def __call__(self, text: str) -> list[str]:
        lines = text.split('\n')
        lined_text = '\n'.join([f'{i}: {line}' for i, line in enumerate(lines)])
        outline = self.extract_outline({"full_text": lined_text})
        outputs = [outline.paper.title]
        print(outline.paper.title)
        for i, section in enumerate(outline.paper.sections):
            print(section.title)
            time.sleep(self.interval)
            end_line = None
            if len(outline.paper.sections) > (i+1):
                end_line = outline.paper.sections[i+1].line
            section_text = '## ' + ('\n'.join(lines[section.line:end_line]))
            if section.is_references:
                try:
                    refs = self.convert_references({'full_text': section_text })
                    output = '\n'.join([str(ref) for ref in refs.references])
                    output = '## 参考文献\n\n' + output
                except Exception as err:
                    output = f'## 参考文献\n\n```\n{err}\n```'
            else:
                try:
                    output = self.translate_single_section({'full_text': section_text })
                    output = self.replace_equation({'full_text': output })
                    output = self.convert_references_source(output)
                except StopCandidateException as e:
                    print('skip this section because\n', e)
                    output = f'## {section.title}\n\n### body\n{section_text}\n\n### error\n```\n{e}\n```'
            outputs.append('\n\n' + output + '\n\n')
        return outputs

def translate_by_gemini(text: str) -> list[str]:
    translator = TranslatePaper()
    return translator(text)

def translate_pdf(pdf_file: str, page_limit: int | None = None, cache_dir: str | None = None) -> list[str]:
    from pypdf import PdfReader
    pdf = PdfReader(pdf_file)
    full_text = ''.join([page.extract_text() for page in pdf.pages])
    return translate_by_gemini(full_text)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str)
    args = parser.parse_args()

    outputs = translate_pdf(args.path)
    breakpoint()

