from app.services.bill_parser import parse_bill_words, ParsedRowList
from app.services.ocr_service import Word

def test_parse_bill_words_without_template_behaves_identically():
    # Simulate a bill with some words
    words = [
        Word(text="PRODUCT", x_min=10, y_min=10, x_max=60, y_max=20),
        Word(text="QTY", x_min=70, y_min=10, x_max=100, y_max=20),
        Word(text="RATE", x_min=110, y_min=10, x_max=140, y_max=20),
        Word(text="BATCH", x_min=150, y_min=10, x_max=180, y_max=20),
        Word(text="PARACETAMOL", x_min=10, y_min=30, x_max=60, y_max=40),
        Word(text="10", x_min=70, y_min=30, x_max=100, y_max=40),
        Word(text="15.5", x_min=110, y_min=30, x_max=140, y_max=40),
        Word(text="B123", x_min=150, y_min=30, x_max=180, y_max=40),
    ]
    
    result = parse_bill_words(words, stored_template=None)
    assert len(result) == 1
    assert result[0].fields["name"] == "PARACETAMOL"
    assert result[0].fields["qty"] == 10.0
    assert result[0].fields["rate"] == 15.5
    assert result[0].fields["batch"] == "B123"
    
    # Check that it returns ParsedRowList with tokens and columns attached
    assert isinstance(result, ParsedRowList)
    assert "PRODUCT" in result.header_tokens
    assert len(result.column_map) == 4

def test_parse_bill_words_with_template_skips_header_search():
    words = [
        Word(text="WEIRDA", x_min=10, y_min=10, x_max=60, y_max=20),
        Word(text="WEIRDB", x_min=70, y_min=10, x_max=100, y_max=20),
        Word(text="WEIRDC", x_min=110, y_min=10, x_max=140, y_max=20),
        Word(text="WEIRDD", x_min=150, y_min=10, x_max=180, y_max=20),
        Word(text="AMOXICILLIN", x_min=10, y_min=30, x_max=60, y_max=40),
        Word(text="5", x_min=70, y_min=30, x_max=100, y_max=40),
        Word(text="20.0", x_min=110, y_min=30, x_max=140, y_max=40),
        Word(text="B456", x_min=150, y_min=30, x_max=180, y_max=40),
    ]
    
    # Without template, heuristic will fail because WEIRDA is not a known header alias
    result_no_template = parse_bill_words(words, stored_template=None)
    assert len(result_no_template) == 0
    
    # With a known template, it should parse correctly
    template = {
        "header_signature": ["WEIRDA", "WEIRDB", "WEIRDC", "WEIRDD"],
        "column_field_map": {"WEIRDA": "name", "WEIRDB": "qty", "WEIRDC": "rate", "WEIRDD": "batch"},
        "sample_count": 5
    }
    
    result_with_template = parse_bill_words(words, stored_template=template)
    assert len(result_with_template) == 1
    assert result_with_template[0].fields["name"] == "AMOXICILLIN"
    assert result_with_template[0].fields["qty"] == 5.0
    assert result_with_template[0].fields["rate"] == 20.0
    assert result_with_template[0].fields["batch"] == "B456"
    assert result_with_template.header_tokens == ["WEIRDA", "WEIRDB", "WEIRDC", "WEIRDD"]
