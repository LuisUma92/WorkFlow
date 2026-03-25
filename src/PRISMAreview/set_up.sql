CREATE TABLE IF NOT EXISTS isn_list (
    id_isn CHAR(4) PRIMARY KEY
);

INSERT INTO     isn_list(id_isn) VALUES 
    ('isan'),
    ('isbn'),
    ('ismn'),
    ('isrn'),
    ('issn'),
    ('iswc');

CREATE TABLE IF NOT EXISTS bib_entries (
    id INT UNSIGNED 
    AUTO_INCREMENT PRIMARY KEY,
    entry_type VARCHAR(100),
    bibkey CHAR(200), 
    database_name CHAR(20),
    accessed DATE,
    institution	VARCHAR(200),
    organization	VARCHAR(200),
    publisher	VARCHAR(200),
    title	VARCHAR(500),
    indextitle	VARCHAR(500),
    booktitle	VARCHAR(500),
    maintitle	VARCHAR(500),
    journaltitle	VARCHAR(200),
    issuetitle	VARCHAR(500),
    eventtitle	VARCHAR(500),
    reprinttitle	VARCHAR(500),
    series	VARCHAR(200),
    issue_volume	CHAR(20),
-- volume
    issue_number	CHAR(20),
-- number
    part	CHAR(20),
    issue	CHAR(20),
    volumes	CHAR(20),
    edition	SMALLINT UNSIGNED,
    version	CHAR(50),
    pubstate	CHAR(100),
    pages	CHAR(20),
    pagetotal	CHAR(20),
    pagination	CHAR(200),
    publication_date	DATE,
-- date
    eventdate	DATE,
    urldate	DATE,
    location	CHAR(100),
    venue	CHAR(200),
    url	TEXT(21844) CHARACTER SET utf8,
    doi	TEXT(21844) CHARACTER SET utf8,
    eid	TEXT(21844) CHARACTER SET utf8,
    eprint	TEXT(21844) CHARACTER SET utf8,
    eprinttype  TEXT(21844) CHARACTER SET utf8,
    addendum	TEXT(21844) CHARACTER SET utf8,
    notes	TEXT(21844) CHARACTER SET utf8,
-- note
    howpublished	TEXT(21844) CHARACTER SET utf8,
    language	CHAR(200),
    isn	CHAR(40),
    isn_type	CHAR(4),
    CONSTRAINT type_of_isn FOREIGN KEY (isn_type) REFERENCES isn_list(id_isn),
    abstract	TEXT(21844) CHARACTER SET utf8,
    annotation	TEXT(21844) CHARACTER SET utf8,
    file_path	TEXT(21844) CHARACTER SET utf8,
-- file
    library	VARCHAR(500),
    label	VARCHAR(500),
    shorthand	VARCHAR(500),
    shorthandintro	TEXT(21844) CHARACTER SET utf8,
    execute_task	TEXT(21844) CHARACTER SET utf8,
    keywords	TEXT(21844) CHARACTER SET utf8,
    options	TEXT(21844) CHARACTER SET utf8,
    ids	VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS author (
    id_author INT UNSIGNED 
    AUTO_INCREMENT PRIMARY KEY,
    first_name CHAR(20),
    last_name VARCHAR(200),
    alias BOOLEAN DEFAULT 0,
    affiliation CHAR(100)
);

CREATE TABLE IF NOT EXISTS author_type (
    id_author_type TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_of_author CHAR(12)
);

INSERT INTO 
    author_type(type_of_author)
VALUES
    ('author'),
    ('bookauthor'),
    ('editor'),
    ('afterword'),
    ('annotator'),
    ('commentator'),
    ('forward'),
    ('introduction'),
    ('translator'),
    ('holder');

CREATE TABLE IF NOT EXISTS bib_author (
    id_author INT UNSIGNED,
    CONSTRAINT author_id FOREIGN KEY (id_author) REFERENCES author (id_author),
    id INT UNSIGNED,
    CONSTRAINT article_id FOREIGN KEY (id) REFERENCES bib_entries (id),
    category TINYINT UNSIGNED,
    CONSTRAINT author_category FOREIGN KEY (category)
    REFERENCES author_type (id_author_type),
    CONSTRAINT author_bib PRIMARY KEY (id_author,id,category),
    first_author BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bib_references (
    article INT UNSIGNED,
    CONSTRAINT source_article FOREIGN KEY (article) REFERENCES bib_entries (id),
    reference INT UNSIGNED,
    CONSTRAINT refered_article FOREIGN KEY (reference) REFERENCES bib_entries (id),
    CONSTRAINT relationship PRIMARY KEY (article,reference)
);

CREATE TABLE IF NOT EXISTS keyword (
    key_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    keyword_list VARCHAR(500) CHARACTER SET utf8
);

CREATE TABLE IF NOT EXISTS reviewed (
    key_id INT UNSIGNED,
    article_id INT UNSIGNED,
    CONSTRAINT key_reference FOREIGN KEY (key_id) REFERENCES keyword (key_id),
    CONSTRAINT article_obtained FOREIGN KEY (article_id) REFERENCES bib_entries (id),
    CONSTRAINT key_assignation PRIMARY KEY  (key_id,article_id),
    retrieved BOOLEAN DEFAULT 0,
    included BOOLEAN DEFAULT 0,
    rationale TEXT(21844) CHARACTER SET utf8
);

CREATE TABLE IF NOT EXISTS abstract (
    id INT UNSIGNED PRIMARY KEY,
    CONSTRAINT article_abstract FOREIGN KEY (id) REFERENCES bib_entries (id),
    objectives TEXT(21844) CHARACTER SET utf8,
    eligibility_criteria TEXT(21844) CHARACTER SET utf8,
    methods_synthesis TEXT(21844) CHARACTER SET utf8,
    results_synthesis TEXT(21844) CHARACTER SET utf8
);

CREATE TABLE IF NOT EXISTS rationale_list (
    rationale_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    rationale_argument VARCHAR(500) CHARACTER SET utf8
);

CREATE TABLE IF NOT EXISTS review_rationale (
    key_id INT UNSIGNED,
    article_id INT UNSIGNED,
    rationale_id INT UNSIGNED,
    CONSTRAINT key_reference FOREIGN KEY (key_id) REFERENCES keyword (key_id),
    CONSTRAINT article_obtained FOREIGN KEY (article_id) REFERENCES bib_entries (id),
    CONSTRAINT rationale_used FOREIGN KEY (rationale_id) REFERENCES rationale_list (id),
    CONSTRAINT key_assignation PRIMARY KEY  (key_id,article_id,rationale_id),
);

CREATE TABLE IF NOT EXISTS tags ();
--
-- Create model Author
--
CREATE TABLE `prismadb_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_name` varchar(20) NOT NULL, `last_name` varchar(200) NOT NULL, `alias` smallint NOT NULL, `affiliation` varchar(100) NOT NULL);
--
-- Create model Author_type
--
CREATE TABLE `prismadb_author_type` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `type_of_author` varchar(12) NOT NULL);
--
-- Create model Isn_list
--
CREATE TABLE `prismadb_isn_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_isn` varchar(4) NOT NULL);
--
-- Create model Keyword
--
CREATE TABLE `prismadb_keyword` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `keyword_list` varchar(500) COLLATE `utf8` NOT NULL);
--
-- Create model Rationale_list
--
CREATE TABLE `prismadb_rationale_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `rationale_argument` varchar(500) COLLATE `utf8` NOT NULL);
--
-- Create model Tags
--
CREATE TABLE `prismadb_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `tag` varchar(200) COLLATE `utf8` NOT NULL);
--
-- Create model Bib_entries
--
CREATE TABLE `prismadb_bib_entries` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `entry_type` varchar(100) NOT NULL, `bibkey` varchar(200) NOT NULL, `database_name` varchar(20) NOT NULL, `accessed` date NOT NULL, `institution` varchar(200) NOT NULL, `organization` varchar(200) NOT NULL, `publisher` varchar(200) NOT NULL, `title` varchar(500) NOT NULL, `indextitle` varchar(500) NOT NULL, `booktitle` varchar(500) NOT NULL, `maintitle` varchar(500) NOT NULL, `journaltitle` varchar(200) NOT NULL, `issuetitle` varchar(500) NOT NULL, `eventtitle` varchar(500) NOT NULL, `reprinttitle` varchar(500) NOT NULL, `series` varchar(200) NOT NULL, `issue_volume` varchar(20) NOT NULL, `issue_number` varchar(20) NOT NULL, `part` varchar(20) NOT NULL, `issue` varchar(20) NOT NULL, `volumes` varchar(20) NOT NULL, `edition` smallint UNSIGNED NOT NULL CHECK (`edition` >= 0), `version` varchar(50) NOT NULL, `pubstate` varchar(100) NOT NULL, `pages` varchar(20) NOT NULL, `pagetotal` varchar(20) NOT NULL, `pagination` varchar(200) NOT NULL, `publication_date` date NOT NULL, `eventdate` date NOT NULL, `urldate` date NOT NULL, `location` varchar(100) NOT NULL, `venue` varchar(200) NOT NULL, `url` longtext COLLATE `utf8` NOT NULL, `doi` longtext COLLATE `utf8` NOT NULL, `eid` longtext COLLATE `utf8` NOT NULL, `eprint` longtext COLLATE `utf8` NOT NULL, `eprinttype` longtext COLLATE `utf8` NOT NULL, `addendum` longtext COLLATE `utf8` NOT NULL, `notes` longtext COLLATE `utf8` NOT NULL, `howpublished` longtext COLLATE `utf8` NOT NULL, `language` varchar(200) NOT NULL, `isn` varchar(40) NOT NULL, `abstract_text` longtext COLLATE `utf8` NOT NULL, `annotation` longtext COLLATE `utf8` NOT NULL, `file_path` longtext COLLATE `utf8` NOT NULL, `library` varchar(500) NOT NULL, `label` varchar(500) NOT NULL, `shorthand` varchar(500) NOT NULL, `shorthandintro` longtext COLLATE `utf8` NOT NULL, `execute_task` longtext COLLATE `utf8` NOT NULL, `keywords` longtext COLLATE `utf8` NOT NULL, `options` longtext COLLATE `utf8` NOT NULL, `ids` varchar(500) NOT NULL, `isn_type_id` bigint NOT NULL);
CREATE TABLE `prismadb_bib_entries_references` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `from_bib_entries_id` bigint NOT NULL, `to_bib_entries_id` bigint NOT NULL);
--
-- Create model Bib_author
--
CREATE TABLE `prismadb_bib_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_author` bool NOT NULL, `category_id` bigint NOT NULL, `id_author_id` bigint NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Abstract
--
CREATE TABLE `prismadb_abstract` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `objectives` longtext COLLATE `utf8` NOT NULL, `eligibility_criteria` longtext COLLATE `utf8` NOT NULL, `methods_synthesis` longtext COLLATE `utf8` NOT NULL, `results_synthesis` longtext COLLATE `utf8` NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Review_rationale
--
CREATE TABLE `prismadb_review_rationale` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL, `id_rationale_id` bigint NOT NULL);
--
-- Create model Reviewed
--
CREATE TABLE `prismadb_reviewed` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `retrieved` smallint NOT NULL, `included` smallint NOT NULL, `rationale` longtext COLLATE `utf8` NOT NULL, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL);
--
-- Create model Article_tags
--
CREATE TABLE `prismadb_article_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_tag_id` bigint NOT NULL);
--
-- Create constraint unique_author_function_per_article on model bib_author
--
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `unique_author_function_per_article` UNIQUE (`id_author_id`, `id_article_id`, `category_id`);
--
-- Create constraint dont_repit_rationale_per_article_per_keyword on model review_rationale
--
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `dont_repit_rationale_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`, `id_rationale_id`);
--
-- Create constraint unique_review_per_article_per_keyword on model reviewed
--
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `unique_review_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`);
--
-- Create constraint dont_repit_tags_per_article on model article_tags
--
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `dont_repit_tags_per_article` UNIQUE (`id_tag_id`, `id_article_id`);
ALTER TABLE `prismadb_bib_entries` ADD CONSTRAINT `prismadb_bib_entries_isn_type_id_7368d6f7_fk_prismadb_` FOREIGN KEY (`isn_type_id`) REFERENCES `prismadb_isn_list` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_ref_from_bib_entries_id_to_b_a9647e09_uniq` UNIQUE (`from_bib_entries_id`, `to_bib_entries_id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_from_bib_entries_id_97e54764_fk_prismadb_` FOREIGN KEY (`from_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_to_bib_entries_id_634f4237_fk_prismadb_` FOREIGN KEY (`to_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_category_id_cb75d03e_fk_prismadb_` FOREIGN KEY (`category_id`) REFERENCES `prismadb_author_type` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_author_id_29555b5c_fk_prismadb_author_id` FOREIGN KEY (`id_author_id`) REFERENCES `prismadb_author` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_article_id_aa5cf037_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_abstract` ADD CONSTRAINT `prismadb_abstract_id_article_id_8faa21bf_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_article_id_46494fcd_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_key_id_2f952faa_fk_prismadb_` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_rationale_id_8a37e20f_fk_prismadb_` FOREIGN KEY (`id_rationale_id`) REFERENCES `prismadb_rationale_list` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_article_id_b5fc27c0_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_key_id_c8f94f33_fk_prismadb_keyword_id` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tag_id_article_id_bcdd747d_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tags_id_tag_id_d5f441d1_fk_prismadb_tags_id` FOREIGN KEY (`id_tag_id`) REFERENCES `prismadb_tags` (`id`);
--
-- Create model Author
--
CREATE TABLE `prismadb_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_name` varchar(20) NOT NULL, `last_name` varchar(200) NOT NULL, `alias` smallint NOT NULL, `affiliation` varchar(100) NOT NULL);
--
-- Create model Author_type
--
CREATE TABLE `prismadb_author_type` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `type_of_author` varchar(12) NOT NULL);
--
-- Create model Isn_list
--
CREATE TABLE `prismadb_isn_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_isn` varchar(4) NOT NULL);
--
-- Create model Keyword
--
CREATE TABLE `prismadb_keyword` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `keyword_list` varchar(500) COLLATE `utf8mb4` NOT NULL);
--
-- Create model Rationale_list
--
CREATE TABLE `prismadb_rationale_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `rationale_argument` varchar(500) COLLATE `utf8mb4` NOT NULL);
--
-- Create model Tags
--
CREATE TABLE `prismadb_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `tag` varchar(200) COLLATE `utf8mb4` NOT NULL);
--
-- Create model Bib_entries
--
CREATE TABLE `prismadb_bib_entries` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `entry_type` varchar(100) NOT NULL, `bibkey` varchar(200) NOT NULL, `database_name` varchar(20) NOT NULL, `accessed` date NOT NULL, `institution` varchar(200) NOT NULL, `organization` varchar(200) NOT NULL, `publisher` varchar(200) NOT NULL, `title` varchar(500) NOT NULL, `indextitle` varchar(500) NOT NULL, `booktitle` varchar(500) NOT NULL, `maintitle` varchar(500) NOT NULL, `journaltitle` varchar(200) NOT NULL, `issuetitle` varchar(500) NOT NULL, `eventtitle` varchar(500) NOT NULL, `reprinttitle` varchar(500) NOT NULL, `series` varchar(200) NOT NULL, `issue_volume` varchar(20) NOT NULL, `issue_number` varchar(20) NOT NULL, `part` varchar(20) NOT NULL, `issue` varchar(20) NOT NULL, `volumes` varchar(20) NOT NULL, `edition` smallint UNSIGNED NOT NULL CHECK (`edition` >= 0), `version` varchar(50) NOT NULL, `pubstate` varchar(100) NOT NULL, `pages` varchar(20) NOT NULL, `pagetotal` varchar(20) NOT NULL, `pagination` varchar(200) NOT NULL, `publication_date` date NOT NULL, `eventdate` date NOT NULL, `urldate` date NOT NULL, `location` varchar(100) NOT NULL, `venue` varchar(200) NOT NULL, `url` longtext COLLATE `utf8mb4` NOT NULL, `doi` longtext COLLATE `utf8mb4` NOT NULL, `eid` longtext COLLATE `utf8mb4` NOT NULL, `eprint` longtext COLLATE `utf8mb4` NOT NULL, `eprinttype` longtext COLLATE `utf8mb4` NOT NULL, `addendum` longtext COLLATE `utf8mb4` NOT NULL, `notes` longtext COLLATE `utf8mb4` NOT NULL, `howpublished` longtext COLLATE `utf8mb4` NOT NULL, `language` varchar(200) NOT NULL, `isn` varchar(40) NOT NULL, `abstract_text` longtext COLLATE `utf8mb4` NOT NULL, `annotation` longtext COLLATE `utf8mb4` NOT NULL, `file_path` longtext COLLATE `utf8mb4` NOT NULL, `library` varchar(500) NOT NULL, `label` varchar(500) NOT NULL, `shorthand` varchar(500) NOT NULL, `shorthandintro` longtext COLLATE `utf8mb4` NOT NULL, `execute_task` longtext COLLATE `utf8mb4` NOT NULL, `keywords` longtext COLLATE `utf8mb4` NOT NULL, `options` longtext COLLATE `utf8mb4` NOT NULL, `ids` varchar(500) NOT NULL, `isn_type_id` bigint NOT NULL);
CREATE TABLE `prismadb_bib_entries_references` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `from_bib_entries_id` bigint NOT NULL, `to_bib_entries_id` bigint NOT NULL);
--
-- Create model Bib_author
--
CREATE TABLE `prismadb_bib_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_author` bool NOT NULL, `category_id` bigint NOT NULL, `id_author_id` bigint NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Abstract
--
CREATE TABLE `prismadb_abstract` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `objectives` longtext COLLATE `utf8mb4` NOT NULL, `eligibility_criteria` longtext COLLATE `utf8mb4` NOT NULL, `methods_synthesis` longtext COLLATE `utf8mb4` NOT NULL, `results_synthesis` longtext COLLATE `utf8mb4` NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Review_rationale
--
CREATE TABLE `prismadb_review_rationale` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL, `id_rationale_id` bigint NOT NULL);
--
-- Create model Reviewed
--
CREATE TABLE `prismadb_reviewed` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `retrieved` smallint NOT NULL, `included` smallint NOT NULL, `rationale` longtext COLLATE `utf8mb4` NOT NULL, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL);
--
-- Create model Article_tags
--
CREATE TABLE `prismadb_article_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_tag_id` bigint NOT NULL);
--
-- Create constraint unique_author_function_per_article on model bib_author
--
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `unique_author_function_per_article` UNIQUE (`id_author_id`, `id_article_id`, `category_id`);
--
-- Create constraint dont_repit_rationale_per_article_per_keyword on model review_rationale
--
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `dont_repit_rationale_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`, `id_rationale_id`);
--
-- Create constraint unique_review_per_article_per_keyword on model reviewed
--
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `unique_review_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`);
--
-- Create constraint dont_repit_tags_per_article on model article_tags
--
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `dont_repit_tags_per_article` UNIQUE (`id_tag_id`, `id_article_id`);
ALTER TABLE `prismadb_bib_entries` ADD CONSTRAINT `prismadb_bib_entries_isn_type_id_7368d6f7_fk_prismadb_` FOREIGN KEY (`isn_type_id`) REFERENCES `prismadb_isn_list` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_ref_from_bib_entries_id_to_b_a9647e09_uniq` UNIQUE (`from_bib_entries_id`, `to_bib_entries_id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_from_bib_entries_id_97e54764_fk_prismadb_` FOREIGN KEY (`from_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_to_bib_entries_id_634f4237_fk_prismadb_` FOREIGN KEY (`to_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_category_id_cb75d03e_fk_prismadb_` FOREIGN KEY (`category_id`) REFERENCES `prismadb_author_type` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_author_id_29555b5c_fk_prismadb_author_id` FOREIGN KEY (`id_author_id`) REFERENCES `prismadb_author` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_article_id_aa5cf037_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_abstract` ADD CONSTRAINT `prismadb_abstract_id_article_id_8faa21bf_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_article_id_46494fcd_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_key_id_2f952faa_fk_prismadb_` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_rationale_id_8a37e20f_fk_prismadb_` FOREIGN KEY (`id_rationale_id`) REFERENCES `prismadb_rationale_list` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_article_id_b5fc27c0_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_key_id_c8f94f33_fk_prismadb_keyword_id` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tag_id_article_id_bcdd747d_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tags_id_tag_id_d5f441d1_fk_prismadb_tags_id` FOREIGN KEY (`id_tag_id`) REFERENCES `prismadb_tags` (`id`);
--
-- Create model Author
--
CREATE TABLE `prismadb_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_name` varchar(20) NOT NULL, `last_name` varchar(200) NOT NULL, `alias` smallint NOT NULL, `affiliation` varchar(100) NOT NULL);
--
-- Create model Author_type
--
CREATE TABLE `prismadb_author_type` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `type_of_author` varchar(12) NOT NULL);
--
-- Create model Isn_list
--
CREATE TABLE `prismadb_isn_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_isn` varchar(4) NOT NULL);
--
-- Create model Keyword
--
CREATE TABLE `prismadb_keyword` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `keyword_list` varchar(500) NOT NULL);
--
-- Create model Rationale_list
--
CREATE TABLE `prismadb_rationale_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `rationale_argument` varchar(500) NOT NULL);
--
-- Create model Tags
--
CREATE TABLE `prismadb_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `tag` varchar(200) COLLATE `utf8mb4` NOT NULL);
--
-- Create model Bib_entries
--
CREATE TABLE `prismadb_bib_entries` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `entry_type` varchar(100) NOT NULL, `bibkey` varchar(200) NOT NULL, `database_name` varchar(20) NOT NULL, `accessed` date NOT NULL, `institution` varchar(200) NOT NULL, `organization` varchar(200) NOT NULL, `publisher` varchar(200) NOT NULL, `title` varchar(500) NOT NULL, `indextitle` varchar(500) NOT NULL, `booktitle` varchar(500) NOT NULL, `maintitle` varchar(500) NOT NULL, `journaltitle` varchar(200) NOT NULL, `issuetitle` varchar(500) NOT NULL, `eventtitle` varchar(500) NOT NULL, `reprinttitle` varchar(500) NOT NULL, `series` varchar(200) NOT NULL, `issue_volume` varchar(20) NOT NULL, `issue_number` varchar(20) NOT NULL, `part` varchar(20) NOT NULL, `issue` varchar(20) NOT NULL, `volumes` varchar(20) NOT NULL, `edition` smallint UNSIGNED NOT NULL CHECK (`edition` >= 0), `version` varchar(50) NOT NULL, `pubstate` varchar(100) NOT NULL, `pages` varchar(20) NOT NULL, `pagetotal` varchar(20) NOT NULL, `pagination` varchar(200) NOT NULL, `publication_date` date NOT NULL, `eventdate` date NOT NULL, `urldate` date NOT NULL, `location` varchar(100) NOT NULL, `venue` varchar(200) NOT NULL, `url` longtext COLLATE `utf8mb4` NOT NULL, `doi` longtext COLLATE `utf8mb4` NOT NULL, `eid` longtext COLLATE `utf8mb4` NOT NULL, `eprint` longtext COLLATE `utf8mb4` NOT NULL, `eprinttype` longtext COLLATE `utf8mb4` NOT NULL, `addendum` longtext COLLATE `utf8mb4` NOT NULL, `notes` longtext COLLATE `utf8mb4` NOT NULL, `howpublished` longtext COLLATE `utf8mb4` NOT NULL, `language` varchar(200) NOT NULL, `isn` varchar(40) NOT NULL, `abstract_text` longtext COLLATE `utf8mb4` NOT NULL, `annotation` longtext COLLATE `utf8mb4` NOT NULL, `file_path` longtext COLLATE `utf8mb4` NOT NULL, `library` varchar(500) NOT NULL, `label` varchar(500) NOT NULL, `shorthand` varchar(500) NOT NULL, `shorthandintro` longtext COLLATE `utf8mb4` NOT NULL, `execute_task` longtext COLLATE `utf8mb4` NOT NULL, `keywords` longtext COLLATE `utf8mb4` NOT NULL, `options` longtext COLLATE `utf8mb4` NOT NULL, `ids` varchar(500) NOT NULL, `isn_type_id` bigint NOT NULL);
CREATE TABLE `prismadb_bib_entries_references` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `from_bib_entries_id` bigint NOT NULL, `to_bib_entries_id` bigint NOT NULL);
--
-- Create model Bib_author
--
CREATE TABLE `prismadb_bib_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_author` bool NOT NULL, `category_id` bigint NOT NULL, `id_author_id` bigint NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Abstract
--
CREATE TABLE `prismadb_abstract` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `objectives` longtext COLLATE `utf8mb4` NOT NULL, `eligibility_criteria` longtext COLLATE `utf8mb4` NOT NULL, `methods_synthesis` longtext COLLATE `utf8mb4` NOT NULL, `results_synthesis` longtext COLLATE `utf8mb4` NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Review_rationale
--
CREATE TABLE `prismadb_review_rationale` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL, `id_rationale_id` bigint NOT NULL);
--
-- Create model Reviewed
--
CREATE TABLE `prismadb_reviewed` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `retrieved` smallint NOT NULL, `included` smallint NOT NULL, `rationale` longtext COLLATE `utf8mb4` NOT NULL, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL);
--
-- Create model Article_tags
--
CREATE TABLE `prismadb_article_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_tag_id` bigint NOT NULL);
--
-- Create constraint unique_author_function_per_article on model bib_author
--
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `unique_author_function_per_article` UNIQUE (`id_author_id`, `id_article_id`, `category_id`);
--
-- Create constraint dont_repit_rationale_per_article_per_keyword on model review_rationale
--
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `dont_repit_rationale_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`, `id_rationale_id`);
--
-- Create constraint unique_review_per_article_per_keyword on model reviewed
--
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `unique_review_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`);
--
-- Create constraint dont_repit_tags_per_article on model article_tags
--
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `dont_repit_tags_per_article` UNIQUE (`id_tag_id`, `id_article_id`);
ALTER TABLE `prismadb_bib_entries` ADD CONSTRAINT `prismadb_bib_entries_isn_type_id_7368d6f7_fk_prismadb_` FOREIGN KEY (`isn_type_id`) REFERENCES `prismadb_isn_list` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_ref_from_bib_entries_id_to_b_a9647e09_uniq` UNIQUE (`from_bib_entries_id`, `to_bib_entries_id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_from_bib_entries_id_97e54764_fk_prismadb_` FOREIGN KEY (`from_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_to_bib_entries_id_634f4237_fk_prismadb_` FOREIGN KEY (`to_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_category_id_cb75d03e_fk_prismadb_` FOREIGN KEY (`category_id`) REFERENCES `prismadb_author_type` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_author_id_29555b5c_fk_prismadb_author_id` FOREIGN KEY (`id_author_id`) REFERENCES `prismadb_author` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_article_id_aa5cf037_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_abstract` ADD CONSTRAINT `prismadb_abstract_id_article_id_8faa21bf_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_article_id_46494fcd_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_key_id_2f952faa_fk_prismadb_` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_rationale_id_8a37e20f_fk_prismadb_` FOREIGN KEY (`id_rationale_id`) REFERENCES `prismadb_rationale_list` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_article_id_b5fc27c0_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_key_id_c8f94f33_fk_prismadb_keyword_id` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tag_id_article_id_bcdd747d_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tags_id_tag_id_d5f441d1_fk_prismadb_tags_id` FOREIGN KEY (`id_tag_id`) REFERENCES `prismadb_tags` (`id`);
--
-- Create model Author
--
CREATE TABLE `prismadb_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_name` varchar(20) NOT NULL, `last_name` varchar(200) NOT NULL, `alias` smallint NOT NULL, `affiliation` varchar(100) NOT NULL);
--
-- Create model Author_type
--
CREATE TABLE `prismadb_author_type` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `type_of_author` varchar(12) NOT NULL);
--
-- Create model Isn_list
--
CREATE TABLE `prismadb_isn_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_isn` varchar(4) NOT NULL);
--
-- Create model Keyword
--
CREATE TABLE `prismadb_keyword` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `keyword_list` varchar(500) NOT NULL);
--
-- Create model Rationale_list
--
CREATE TABLE `prismadb_rationale_list` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `rationale_argument` varchar(500) NOT NULL);
--
-- Create model Tags
--
CREATE TABLE `prismadb_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `tag` varchar(200) COLLATE `utf8mb4` NOT NULL);
--
-- Create model Bib_entries
--
CREATE TABLE `prismadb_bib_entries` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `entry_type` varchar(100) NOT NULL, `bibkey` varchar(200) NOT NULL, `database_name` varchar(20) NOT NULL, `accessed` date NOT NULL, `institution` varchar(200) NOT NULL, `organization` varchar(200) NOT NULL, `publisher` varchar(200) NOT NULL, `title` varchar(500) NOT NULL, `indextitle` varchar(500) NOT NULL, `booktitle` varchar(500) NOT NULL, `maintitle` varchar(500) NOT NULL, `journaltitle` varchar(200) NOT NULL, `issuetitle` varchar(500) NOT NULL, `eventtitle` varchar(500) NOT NULL, `reprinttitle` varchar(500) NOT NULL, `series` varchar(200) NOT NULL, `issue_volume` varchar(20) NOT NULL, `issue_number` varchar(20) NOT NULL, `part` varchar(20) NOT NULL, `issue` varchar(20) NOT NULL, `volumes` varchar(20) NOT NULL, `edition` smallint UNSIGNED NOT NULL CHECK (`edition` >= 0), `version` varchar(50) NOT NULL, `pubstate` varchar(100) NOT NULL, `pages` varchar(20) NOT NULL, `pagetotal` varchar(20) NOT NULL, `pagination` varchar(200) NOT NULL, `publication_date` date NOT NULL, `eventdate` date NOT NULL, `urldate` date NOT NULL, `location` varchar(100) NOT NULL, `venue` varchar(200) NOT NULL, `url` longtext COLLATE `utf8mb4` NOT NULL, `doi` longtext COLLATE `utf8mb4` NOT NULL, `eid` longtext COLLATE `utf8mb4` NOT NULL, `eprint` longtext COLLATE `utf8mb4` NOT NULL, `eprinttype` longtext COLLATE `utf8mb4` NOT NULL, `addendum` longtext COLLATE `utf8mb4` NOT NULL, `notes` longtext COLLATE `utf8mb4` NOT NULL, `howpublished` longtext COLLATE `utf8mb4` NOT NULL, `language` varchar(200) NOT NULL, `isn` varchar(40) NOT NULL, `abstract_text` longtext COLLATE `utf8mb4` NOT NULL, `annotation` longtext COLLATE `utf8mb4` NOT NULL, `file_path` longtext COLLATE `utf8mb4` NOT NULL, `library` varchar(500) NOT NULL, `label` varchar(500) NOT NULL, `shorthand` varchar(500) NOT NULL, `shorthandintro` longtext COLLATE `utf8mb4` NOT NULL, `execute_task` longtext COLLATE `utf8mb4` NOT NULL, `keywords` longtext COLLATE `utf8mb4` NOT NULL, `options` longtext COLLATE `utf8mb4` NOT NULL, `ids` varchar(500) NOT NULL, `isn_type_id` bigint NOT NULL);
CREATE TABLE `prismadb_bib_entries_references` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `from_bib_entries_id` bigint NOT NULL, `to_bib_entries_id` bigint NOT NULL);
--
-- Create model Bib_author
--
CREATE TABLE `prismadb_bib_author` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `first_author` bool NOT NULL, `category_id` bigint NOT NULL, `id_author_id` bigint NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Abstract
--
CREATE TABLE `prismadb_abstract` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `objectives` longtext COLLATE `utf8mb4` NOT NULL, `eligibility_criteria` longtext COLLATE `utf8mb4` NOT NULL, `methods_synthesis` longtext COLLATE `utf8mb4` NOT NULL, `results_synthesis` longtext COLLATE `utf8mb4` NOT NULL, `id_article_id` bigint NOT NULL);
--
-- Create model Review_rationale
--
CREATE TABLE `prismadb_review_rationale` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL, `id_rationale_id` bigint NOT NULL);
--
-- Create model Reviewed
--
CREATE TABLE `prismadb_reviewed` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `retrieved` smallint NOT NULL, `included` smallint NOT NULL, `rationale` longtext COLLATE `utf8mb4` NOT NULL, `id_article_id` bigint NOT NULL, `id_key_id` bigint NOT NULL);
--
-- Create model Article_tags
--
CREATE TABLE `prismadb_article_tags` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `id_article_id` bigint NOT NULL, `id_tag_id` bigint NOT NULL);
--
-- Create constraint unique_author_function_per_article on model bib_author
--
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `unique_author_function_per_article` UNIQUE (`id_author_id`, `id_article_id`, `category_id`);
--
-- Create constraint dont_repit_rationale_per_article_per_keyword on model review_rationale
--
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `dont_repit_rationale_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`, `id_rationale_id`);
--
-- Create constraint unique_review_per_article_per_keyword on model reviewed
--
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `unique_review_per_article_per_keyword` UNIQUE (`id_key_id`, `id_article_id`);
--
-- Create constraint dont_repit_tags_per_article on model article_tags
--
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `dont_repit_tags_per_article` UNIQUE (`id_tag_id`, `id_article_id`);
ALTER TABLE `prismadb_bib_entries` ADD CONSTRAINT `prismadb_bib_entries_isn_type_id_7368d6f7_fk_prismadb_` FOREIGN KEY (`isn_type_id`) REFERENCES `prismadb_isn_list` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_ref_from_bib_entries_id_to_b_a9647e09_uniq` UNIQUE (`from_bib_entries_id`, `to_bib_entries_id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_from_bib_entries_id_97e54764_fk_prismadb_` FOREIGN KEY (`from_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_entries_references` ADD CONSTRAINT `prismadb_bib_entries_to_bib_entries_id_634f4237_fk_prismadb_` FOREIGN KEY (`to_bib_entries_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_category_id_cb75d03e_fk_prismadb_` FOREIGN KEY (`category_id`) REFERENCES `prismadb_author_type` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_author_id_29555b5c_fk_prismadb_author_id` FOREIGN KEY (`id_author_id`) REFERENCES `prismadb_author` (`id`);
ALTER TABLE `prismadb_bib_author` ADD CONSTRAINT `prismadb_bib_author_id_article_id_aa5cf037_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_abstract` ADD CONSTRAINT `prismadb_abstract_id_article_id_8faa21bf_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_article_id_46494fcd_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_key_id_2f952faa_fk_prismadb_` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_review_rationale` ADD CONSTRAINT `prismadb_review_rati_id_rationale_id_8a37e20f_fk_prismadb_` FOREIGN KEY (`id_rationale_id`) REFERENCES `prismadb_rationale_list` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_article_id_b5fc27c0_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_reviewed` ADD CONSTRAINT `prismadb_reviewed_id_key_id_c8f94f33_fk_prismadb_keyword_id` FOREIGN KEY (`id_key_id`) REFERENCES `prismadb_keyword` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tag_id_article_id_bcdd747d_fk_prismadb_` FOREIGN KEY (`id_article_id`) REFERENCES `prismadb_bib_entries` (`id`);
ALTER TABLE `prismadb_article_tags` ADD CONSTRAINT `prismadb_article_tags_id_tag_id_d5f441d1_fk_prismadb_tags_id` FOREIGN KEY (`id_tag_id`) REFERENCES `prismadb_tags` (`id`);
