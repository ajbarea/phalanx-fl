# Test script for Huggingface text datasets integration
from intellifl.dataset_loaders.huggingface_text_dataset_loader import HuggingFaceTextDatasetLoader

DATASETS = [
    {
        "name": "financial_phrasebank",
        "hf_dataset_path": "gtfintechlab/financial_phrasebank_sentences_allagree",
        "hf_dataset_name": "5768",
        "tokenize_columns": ["sentence"],
    },
    {
        "name": "lexglue",
        "hf_dataset_path": "coastalcph/lex_glue",
        "hf_dataset_name": "ledgar",
        "tokenize_columns": ["text"],
    },
    {
        "name": "pubmed_classification_20k",
        "hf_dataset_path": "ml4pubmed/pubmed-classification-20k",
        "hf_dataset_name": None,
        "tokenize_columns": ["text"],
    },
    {
        "name": "medal",
        "hf_dataset_path": "cyrilzakka/pubmed-medline",
        "hf_dataset_name": None,
        "tokenize_columns": [
            "id", "pubmed_id", "title", "authors", "journal", "content", "source_url", "publication_types"
        ],
    },
]


def test_loader(dataset_info):
    print(f"\nTesting {dataset_info['name']}...")
    try:
        loader = HuggingFaceTextDatasetLoader(
            hf_dataset_path=dataset_info["hf_dataset_path"],
            hf_dataset_name=dataset_info["hf_dataset_name"],
            tokenize_columns=dataset_info["tokenize_columns"],
            num_of_clients=2,
            max_samples=100,  # limit for quick test
        )
        trainloaders, valloaders = loader.load_datasets()
        print(f"Success: {len(trainloaders)} trainloaders, {len(valloaders)} valloaders")
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    for ds in DATASETS:
        test_loader(ds)
