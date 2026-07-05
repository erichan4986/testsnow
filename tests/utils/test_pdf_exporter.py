from scripts.utils.pdf_exporter import _md_to_html


def test_pdf_html_constrains_report_images_for_a4_pages():
    html = _md_to_html("![技术面分析](/tmp/technical.png)")

    assert "img {" in html
    assert "max-width: 100%;" in html
    assert "max-height: 210mm;" in html
    assert "object-fit: contain;" in html
