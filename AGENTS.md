# AGENTS.md

# Project

Doclingを利用してPDFなどの文書を画像付きMarkdownへ変換するライブラリ。

## Goals

- CLIとFastAPIの両方を提供する。
- Markdownと画像を同時に出力する。
- Docker環境で動作する。
- GPUが利用できない場合はCPUへ自動フォールバックする。

## Architecture

- CLIとFastAPIは同一の変換パイプラインを利用する。
- Doclingを標準の変換バックエンドとする。
- 高コストなコンポーネントは再利用する。
- Markdown出力形式との互換性を維持する。

## Constraints

- 新しい変換処理を追加する前に既存実装を再利用する。
- CLIとFastAPIで出力結果を一致させる。
- 外部入力は必ず検証する。
- ユーザーが見える仕様を変更した場合はREADMEを更新する。

## Development

- Python依存関係は `uv` と `pyproject.toml` で管理する。
- 変更にはテストを追加または更新する。
- 実装方針は `docs/` を参照する。

## Python Environment

- Use `uv` for all Python workflows.
- Run Python commands with `uv run`.
- Use `uv add` / `uv remove` to manage dependencies.
- Never use `pip install`.
- Never use `uv pip install --global`.
- Never modify the global Python environment.
- Keep all dependencies declared in `pyproject.toml` and the lockfile.

## References

- https://docling-project.github.io/docling/