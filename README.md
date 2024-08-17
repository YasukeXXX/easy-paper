
# easy-paper

**どうしても日本語で論文を読みたい**

- 結局日本語で読むのが一番効率的なので翻訳しつつマークダウンに変換します
- 自分用に作っているので参考程度に

## 自分の使い方
1. [Notion Web Clipper](https://www.notion.so/ja/web-clipper) で特定の Notion データベースに arxiv ページをためておく
1. easy-paper を起動
	- `python -m src.app --github_repository=xxx/xxx --github_path=path/`
	- 以下が実行される
		- Notion から arxiv のリストを取得
		- Gemini or Claude で翻訳
		- (github repostory を渡している場合)
		  - マークダウンを GitHub にプッシュ
		- 翻訳した内容をNotion に保存

1. GitHub につなげてる Obsidian から論文を読む
	- Notion 用にブロックタイプ色々対応するのが面倒過ぎるので、Obsidian でプレーンなマークダウンとして参照してる
	- 数式も綺麗に読める (重要)

## 必要なもの
以下を環境変数にセット

- `NOTION_REFERENCE_DB`: 論文を溜める Notion データベースの id
  - そのまま動かすには、`URL`, `Created`, `Translate Status` カラムが存在する必要がある
- `NOTION_SECRET`: Notion の API key
- `GEMINI_API_KEY`: Gemini の API key
- `ANTHROPIC_API_KEY`: anthoropic の API key (claude を使う場合)
- `GITHUB_TOKEN`: GitHub Token (GitHub を使う場合)

