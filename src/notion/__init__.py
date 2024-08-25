import os
from notion_client import Client
from notion_client.helpers import iterate_paginated_api

NOTION_CLIENT = Client(auth=os.environ["NOTION_SECRET"])

def get_func_name(fn) -> str:
    if hasattr(fn, '__name__'):
        return fn.__name__
    if isinstance(fn, classmethod):
        return get_func_name(fn.__func__)
    if isinstance(fn, property):
        return get_func_name(fn.fget)

def db(database_id: str):
    def decolate(cls):
        cls.database_id = database_id

        @classmethod
        @property
        def schema(cls) -> dict:
            if not hasattr(cls, '_schema'):
                cls._schema = NOTION_CLIENT.databases.retrieve(database_id=cls.database_id)
            return cls._schema

        @classmethod
        @property
        def properties(cls) -> dict:
            return cls.schema['properties']

        @classmethod
        def property_id_of(cls, name: str) -> str:
            if name not in cls.properties:
                raise Exception(f'Database is not have {name} property')
            return cls.properties[name]['id']

        @classmethod
        def query(cls, filter: dict | None = None, select: list[str] | None = None, sorts: list[dict] | None = None, iterate: bool = True):
            options = {}
            if filter is not None:
                options['filter'] = filter

            if select is not None:
                options['filter_properties'] = [cls.property_id_of(col) for col in select]

            if sorts is not None:
                options['sorts'] = sorts

            if not iterate:
                return NOTION_CLIENT.databases.query(
                        database_id=cls.database_id,
                        **options,
                    )
            return iterate_paginated_api(NOTION_CLIENT.databases.query, database_id=cls.database_id, **options)

        funcs = [schema, properties, property_id_of, query]
        for fn in funcs:
            setattr(cls, get_func_name(fn), fn)
        return cls
    return decolate

def append_text_block(block_id: str, texts: list[str]):
    def valid_texts(text: str, max_length: int = 2000) -> list[dict]:
        if len(text) <= max_length:
            return [{ 'type': 'text', 'text': { 'content': text }}]
        return [
                { 'type': 'text', 'text': { 'content': text[i:i+max_length] }}
            for i in range(0, len(text), max_length)]

    payloads = [
            {
                'object': "block",
                'type': "paragraph",
                'paragraph': {
                    'rich_text': valid_texts(text),
                },
            }
        for text in texts]
    return NOTION_CLIENT.blocks.children.append(
            block_id=block_id,
            children=payloads,
        )
