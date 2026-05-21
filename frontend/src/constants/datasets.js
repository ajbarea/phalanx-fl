/**
 * Dataset Constants
 */

export const DATASETS = [
  'cifar100',
  'femnist_iid',
  'femnist_niid',
  'pneumoniamnist',
  'bloodmnist',
  'medquad',
  'financial_phrasebank',
  'lexglue',
  'medal',
  'pubmed_classification_20k',
  'breastmnist',
  'pathmnist',
  'dermamnist',
  'octmnist',
  'retinamnist',
  'tissuemnist',
  'organamnist',
  'organcmnist',
  'organsmnist',
];

// HuggingFace NLP datasets
export const HUGGINGFACE_DATASETS = [
  {
    value: 'financial_phrasebank',
    label: 'Financial PhraseBank',
    hfPath: 'takala/financial_phrasebank',
    hfName: 'sentences_allagree',
    textColumns: ['sentence'],
  },
  {
    value: 'lexglue',
    label: 'LexGLUE LEDGAR',
    hfPath: 'coastalcph/lex_glue',
    hfName: 'ledgar',
    textColumns: ['text'],
  },
  {
    value: 'medal',
    label: 'PubMed MEDLINE',
    hfPath: 'cyrilzakka/pubmed-medline',
    hfName: null,
    textColumns: ['content'],
  },
];
