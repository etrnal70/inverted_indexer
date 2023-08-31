from typing import Any
import pymysql
import pymysql.cursors
import os


class Database:
    """
    Kelas yang digunakan untuk melakukan pengoperasian database.
    """

    def __init__(self) -> None:
        self.host: str = str(os.getenv("DB_HOST"))
        self.username: str = str(os.getenv("DB_USERNAME"))
        self.password: str = str(os.getenv("DB_PASSWORD"))
        self.db_name: str = str(os.getenv("DB_NAME"))
        self.db_port: int = int(str(os.getenv("DB_PORT")))

    def connect(self) -> pymysql.Connection:
        """
        Fungsi untuk melakukan koneksi ke database.

        Returns:
            pymysql.Connection: Koneksi database MySQL
        """
        connection = pymysql.connect(
            host=self.host,
            user=self.username,
            passwd=self.password,
            db=self.db_name,
            port=self.db_port,
            autocommit=True,
        )
        return connection

    def close_connection(self, connection: pymysql.Connection) -> None:
        """
        Fungsi untuk menutup koneksi ke database.

        Args:
            connection (pymysql.Connection): Koneksi database MySQL
        """
        try:
            connection.close()
        except:
            pass

    def check_value_in_table(self, connection: pymysql.Connection,
                             table_name: str, column_name: str, value: Any):
        """
        Fungsi yang berfungsi untuk mengecek keberadaan suatu nilai di dalam tabel dan kolom.

        Args:
            connection (pymysql.Connection): Koneksi database MySQL
            table_name (str): Nama tabel
            column_name (str): Nama kolom
            value (Any): Nilai yang ingin dicek

        Returns:
            bool: True jika ada, False jika tidak ada
        """
        connection.ping()
        db_cursor = connection.cursor()
        db_cursor.execute(
            "SELECT {column}, COUNT(*) FROM {table} WHERE {column} = '{value}' GROUP BY {column}"
            .format(table=table_name, column=column_name, value=value))
        db_cursor.fetchall()
        row_count = db_cursor.rowcount
        db_cursor.close()
        if row_count < 1:
            return False
        return True

    def count_rows(self, connection: pymysql.Connection, table_name: str):
        """
        Fungsi untuk menghitung jumlah baris pada tabel.

        Args:
            connection (pymysql.Connection): Koneksi database MySQL
            table_name (str): Nama tabel

        Returns:
            int: Jumlah baris dari tabel
        """
        connection.ping()
        db_cursor = connection.cursor()
        db_cursor.execute(
            "SELECT COUNT(*) FROM {table}".format(table=table_name))
        row_count = db_cursor.fetchone()[0]
        db_cursor.close()
        return row_count

    def exec_query(self, connection: pymysql.Connection, query: str):
        """
        Fungsi untuk eksekusi query pada database.

        Args:
            connection (pymysql.Connection): Koneksi database MySQL
            query (str): Kueri MySQL
        """
        connection.ping()
        db_cursor = connection.cursor()
        db_cursor.execute(query)
        db_cursor.close()

    def truncate_tables(self):
        """
        Fungsi untuk mengosongkan semua table yang ada di database.
        """
        connection = self.connect()

        try:
            self.exec_query(
                connection,
                "DELETE FROM `tfidf`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `tfidf_word`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `pagerank_changes`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `pagerank`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_linking`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_images`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_tables`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_styles`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_scripts`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_paragraph`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_list`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_forms`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `page_information`",
            )
            self.exec_query(
                connection,
                "DELETE FROM `crawling`",
            )
        except:
            return

        self.close_connection(connection)

    def create_tables(self):
        """
        Fungsi untuk membuat tabel-tabel yang diperlukan di database.
        """

        connection = self.connect()

        try:
            self.exec_query(
                connection,
                "CREATE TABLE `crawling` ( `id_crawling` int PRIMARY KEY AUTO_INCREMENT, `start_urls` text, `keyword` text, `total_page` int, `duration_crawl` time, `created_at` timestamp )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_information` ( `id_page` int PRIMARY KEY AUTO_INCREMENT, `crawl_id` int, `url` text, `html5` tinyint, `title` text, `description` text, `keywords` text, `content_text` longtext, `hot_url` tinyint, `size_bytes` bigint, `model_crawl` text, `duration_crawl` time, `created_at` timestamp )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_linking` ( `id_linking` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `outgoing_link` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_images` ( `id_image` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `image` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_tables` ( `id_table` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `table_str` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_styles` ( `id_style` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `style` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_scripts` ( `id_script` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `script` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_paragraph` ( `id_list` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `paragraph` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_list` ( `id_list` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `list` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `page_forms` ( `id_form` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `form` text )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `tfidf` ( `id_tfidf` int PRIMARY KEY AUTO_INCREMENT, `keyword` text, `page_id` int, `tfidf_total` double )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `tfidf_word` ( `id_word` int PRIMARY KEY AUTO_INCREMENT, `word` text, `page_id` int, `tfidf_score` double )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `pagerank` ( `id_pagerank` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `pagerank_score` double )",
            )
            self.exec_query(
                connection,
                "CREATE TABLE `pagerank_changes` ( `id_change` int PRIMARY KEY AUTO_INCREMENT, `page_id` int, `iteration` int, `pagerank_change` double )",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_information` ADD CONSTRAINT `pageinfo_crawl` FOREIGN KEY (`crawl_id`) REFERENCES `crawling` (`id_crawling`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_linking` ADD CONSTRAINT `pagelink_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_images` ADD CONSTRAINT `pageimage_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_tables` ADD CONSTRAINT `pagetable_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_styles` ADD CONSTRAINT `pagestyle_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_scripts` ADD CONSTRAINT `pagescript_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_paragraph` ADD CONSTRAINT `pagelist_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_list` ADD CONSTRAINT `pagelist_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `page_forms` ADD CONSTRAINT `pageform_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `tfidf` ADD CONSTRAINT `tfidf_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `tfidf_word` ADD CONSTRAINT `tfidfw_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `pagerank` ADD CONSTRAINT `pagerank_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
            self.exec_query(
                connection,
                "ALTER TABLE `pagerank_changes` ADD CONSTRAINT `pagerankc_pageinfo` FOREIGN KEY (`page_id`) REFERENCES `page_information` (`id_page`) ON DELETE CASCADE",
            )
        except:
            return

        self.close_connection(connection)
