from __future__ import annotations

import unittest
from unittest.mock import Mock

from backend.database import (
    CompatCursor,
    _PARTIAL_UNIQUE_RE,
    _index_columns,
    _split_statements,
    _translate_create_table,
    _translate_sql,
)


class DatabaseTranslationTests(unittest.TestCase):
    def test_compat_cursor_supports_iteration(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [{"code": "A"}, {"code": "B"}, None]
        self.assertEqual([row["code"] for row in CompatCursor(cursor)], ["A", "B"])

    def test_rewrites_sqlite_insert_ignore_and_upsert(self):
        sql = "INSERT OR IGNORE INTO items(id,name) VALUES (?,?)"
        self.assertEqual(_translate_sql(sql), "INSERT IGNORE INTO items(id,name) VALUES (%s,%s)")

        upsert = "INSERT INTO items(id,name) VALUES (:id,:name) ON CONFLICT(id) DO UPDATE SET name=excluded.name"
        translated = _translate_sql(upsert)
        self.assertEqual(
            translated,
            "INSERT INTO items(id,name) VALUES (%(id)s,%(name)s) ON DUPLICATE KEY UPDATE name=VALUES(name)",
        )

    def test_placeholder_rewrite_skips_quoted_question_marks_and_colons(self):
        sql = "SELECT ?, '?', 'https://host/a:b', `column?` FROM items WHERE id=:item_id"
        self.assertEqual(
            _translate_sql(sql),
            "SELECT %s, '?', 'https://host/a:b', `column?` FROM items WHERE id=%(item_id)s",
        )

    def test_schema_translator_uses_varchar_for_keys_and_longtext_for_content(self):
        script = """
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL REFERENCES owners(id),
                title TEXT NOT NULL UNIQUE,
                body TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS media_status_title_idx ON media(status,title DESC);
        """
        statements = _split_statements(script)
        indexes = _index_columns(statements)
        translated = _translate_create_table(statements[0], indexes)
        self.assertIn("id VARCHAR(191) PRIMARY KEY", translated)
        self.assertIn("owner_id VARCHAR(191) NOT NULL", translated)
        self.assertIn("FOREIGN KEY (`owner_id`) REFERENCES `owners` (`id`)", translated)
        self.assertIn("title VARCHAR(191) NOT NULL UNIQUE", translated)
        self.assertIn("body LONGTEXT NOT NULL", translated)
        self.assertNotIn("body LONGTEXT NOT NULL DEFAULT", translated)
        self.assertIn("status VARCHAR(191) NOT NULL", translated)

    def test_long_text_defaults_are_removed_but_short_text_defaults_are_kept(self):
        script = """CREATE TABLE IF NOT EXISTS records (
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'READY',
            connection_message TEXT NOT NULL DEFAULT 'not checked'
        )"""
        translated = _translate_create_table(script, {})
        self.assertIn("description LONGTEXT NOT NULL", translated)
        self.assertNotIn("description LONGTEXT NOT NULL DEFAULT", translated)
        self.assertIn("status VARCHAR(191) NOT NULL DEFAULT 'READY'", translated)
        self.assertIn("connection_message VARCHAR(512) NOT NULL DEFAULT 'not checked'", translated)

    def test_table_level_composite_keys_convert_each_text_key_column(self):
        sql = """CREATE TABLE IF NOT EXISTS links (
            left_id TEXT NOT NULL,
            right_id TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY(left_id,right_id)
        )"""
        translated = _translate_create_table(sql, {})
        self.assertIn("left_id VARCHAR(191) NOT NULL", translated)
        self.assertIn("right_id VARCHAR(191) NOT NULL", translated)
        self.assertIn("notes VARCHAR(191) NOT NULL DEFAULT '[]'", translated)

    def test_partial_unique_index_for_nonempty_codes_is_recognized(self):
        statement = "CREATE UNIQUE INDEX IF NOT EXISTS departments_code_unique_idx ON departments(code) WHERE code <> ''"
        self.assertIsNotNone(_PARTIAL_UNIQUE_RE.match(statement))


if __name__ == "__main__":
    unittest.main()
