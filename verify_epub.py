import os
import sys
from app.services.epub_processor import EpubProcessor
from ebooklib import epub

# Create a dummy EPUB
def create_dummy_epub(filename):
    book = epub.EpubBook()
    
    # set metadata
    book.set_identifier('id123456')
    book.set_title('Test EPUB Title')
    book.set_language('en')
    book.add_author('Test Author')

    # create chapter
    c1 = epub.EpubHtml(title='Intro', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Introduction</h1><p>This is a paragraph in the test EPUB.</p>'
    book.add_item(c1)

    # define Table Of Contents
    book.toc = (epub.Link('chap_01.xhtml', 'Introduction', 'intro'),
                 (epub.Section('Simple Chapter'), (c1, ))
                )

    # add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # define CSS style
    style = 'BODY {color: white;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    # basic spine
    book.spine = ['nav', c1]

    # write to the file
    epub.write_epub(filename, book, {})
    print(f"Created {filename}")

def test_processing():
    filename = 'test.epub'
    create_dummy_epub(filename)
    
    try:
        processor = EpubProcessor()
        pages, metadata = processor.process(filename)
        
        print("\n--- Metadata ---")
        print(metadata)
        
        print("\n--- Content ---")
        for page in pages:
            print(f"Page {page['page']}: {page['text']}")
            
        # Verify
        assert metadata['title'] == 'Test EPUB Title'
        assert metadata['author'] == 'Test Author'
        assert 'Introduction' in pages[0]['text']
        print("\nSUCCESS: Verification passed!")
        
    except Exception as e:
        print(f"\nFAILED: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    test_processing()
