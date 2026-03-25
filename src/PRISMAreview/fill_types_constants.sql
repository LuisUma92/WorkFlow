INSERT INTO
    prismadb_isn_list(id_isn)
VALUES 
    ('isan'),
    ('isbn'),
    ('ismn'),
    ('isrn'),
    ('issn'),
    ('iswc');

INSERT INTO 
    prismadb_author_type(type_of_author)
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

INSERT INTO
    prismadb_referenced_databases(name,proxy,aliases)
VALUES
    ('American Physical Society', 'https://aps.proxyucr.elogim.com', 'American Physical Society,APS'),
    ('EBSCO', 'https://ebsco.proxyucr.elogim.com', 'EBSCO'),
    ('IOPscience', 'https://iopscience.proxyucr.elogim.com', 'IOPscience'),
    ('Nature Portafolio', 'https://nature.proxyucr.elogim.com', 'Nature'),
    ('Oxford Academic', 'https://oxfordjournals.proxyucr.elogim.com', 'Oxford Academic,oxfordacademic,oxfordjournals,oxfordbooks'),
    ('ScienceDirect', 'https://sciencedirect.proxyucr.elogim.com', 'ScienceDirect'),
    ('Scopus', 'https://scopus.proxyucr.elogim.com', 'Scopus'),
    ('Springer Link', 'https://springerlink.proxyucr.elogim.com', 'Springer Link,springer,springerlink'),
    ('Taylor \& Francis', 'https://tandfonline.proxyucr.elogim.com', 'Taylor \& Francis,TaylorFrancis,tandf,tandfonline,'),
    ('Wiley Online Library', 'https://wiley.proxyucr.elogim.com', 'Wiley Online Library,Wiley,');
