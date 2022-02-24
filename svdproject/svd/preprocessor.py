import urllib
from nltk.stem.porter import PorterStemmer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from typing import List, Any, Tuple, Generator, Dict
import pickle
import os
import pathlib
import progressbar
import numpy as np
import scipy.sparse as sparse
import scipy.sparse.linalg
from sklearn.preprocessing import normalize
from enum import Enum
from django.contrib.staticfiles import finders


class FT(Enum):
    # file type
    indexed_filenames_dict = 'indexed_filenames_DICT'
    indexed_filenames_list = 'indexed_filenames_LIST'
    preprocessed_data_dir = 'bbc_data_preprocessed'
    indexed_terms = 'indexed_terms'
    tbd_matrix = 'tbd_matrix'
    tbd_matrix_not_norm = 'tbd_matrix_not_norm'
    tbd_idf_matrix = 'tbd_idf_matrix'
    # filenames will have appended _k where k is order of low rank approx
    tbd_svd_matrix = 'tbd_svd_matrix'
    tbd_idf_svd_matrix = 'tbd_idf_svd_matrix'


class Preprocessor:
    RAW_DATA_DIR = finders.find('svd/bbc_data')
    PICKLE_DIR = finders.find('svd/.pickled')

    def __init__(self, stemmer: Any = None, stop_words: List[str] = None) -> None:
        self.paths = {filetype: pathlib.Path(
            self.PICKLE_DIR, filetype.value) for filetype in FT}

        self.files = {filetype: None for filetype in FT}

        if not os.path.isdir(self.paths[FT.preprocessed_data_dir]):
            os.mkdir(self.paths[FT.preprocessed_data_dir])

        self.stemmer = PorterStemmer() if stemmer is None else stemmer

        self.stop_words = stopwords.words(
            'english') if stop_words is None else stop_words
        self.stop_words = set(self.stop_words)

        self.svd_orders = {
            FT.tbd_svd_matrix: None,
            FT.tbd_idf_svd_matrix: None
        }

    def _load_it(self, filetype: FT) -> None:
        self.files[filetype] = load_binary(self.paths[filetype])

    def _save_it(self, filetype: FT, data: Any) -> None:
        self.files[filetype] = data
        save_binary(self.paths[filetype], data)

    def index_documents(self) -> None:
        indexed_filenames_dict = {}
        indexed_filenames_list = []

        with os.scandir(self.RAW_DATA_DIR) as raw_entries:
            for i, entry in enumerate(raw_entries):
                indexed_filenames_dict[entry.name] = i
                indexed_filenames_list.append(entry.name)

        self._save_it(FT.indexed_filenames_dict, indexed_filenames_dict)
        self._save_it(FT.indexed_filenames_list, indexed_filenames_list)

        print(
            f'saved filename indices at {self.paths[FT.indexed_filenames_dict]}' +
            f'and {self.paths[FT.indexed_filenames_list]}')

    def preprocess_docs(self, stem=True, remove_stop_words=True,
                        only_alnum=True, ignore_case=True) -> None:
        print('preprocessing...')

        with os.scandir(self.RAW_DATA_DIR) as raw_entires:
            raw_entires = list(raw_entires)
            bar = progressbar.ProgressBar(maxval=len(raw_entires))
            bar.start()
            for i, entry in enumerate(raw_entires):
                with open(pathlib.Path(self.RAW_DATA_DIR, entry.name), 'r') as f:
                    data = f.read()
                    tokens = self._preprocess_doc(
                        data, stem, remove_stop_words, only_alnum, ignore_case)

                f_path = pathlib.Path(
                    self.paths[FT.preprocessed_data_dir], entry.name)
                save_binary(f_path, tokens)

                bar.update(i+1)
            bar.finish()

        print(
            f'saved preprocessed documents at {self.paths[FT.preprocessed_data_dir]}/*')

    def _preprocess_doc(self, doc: str, stem: bool = True, remove_stop_words: bool = True,
                        only_alnum: bool = True, ignore_case: bool = True) -> List[str]:
        tokens = word_tokenize(doc)

        # transform to lower case
        if ignore_case:
            tokens = [token.lower() for token in tokens]

        # filter not alpha numeric tokens
        if only_alnum:
            tokens = [token for token in tokens if token.isalnum()]

        # filter stop words
        if remove_stop_words:
            tokens = [token for token in tokens if token not in self.stop_words]

        # stem words
        if stem:
            tokens = [self.stemmer.stem(token) for token in tokens]

        return tokens

    def index_terms(self) -> None:
        indexed_terms = {}
        count = 0
        for _, doc in self.get_preprocessed_docs():
            for token in doc:
                if token not in indexed_terms:
                    indexed_terms[token] = count
                    count += 1

        self._save_it(FT.indexed_terms, indexed_terms)

        print(
            f'saved indexed terms at {self.paths[FT.indexed_terms]}')

    def _build_tbd(self):
        indexed_docs, _ = self.get_doc_indices()
        indexed_terms = self.get_indexed_terms()

        N = len(indexed_docs)
        M = len(indexed_terms)

        tbd_matrix = sparse.lil_matrix((M, N))

        for name, doc in self.get_preprocessed_docs():
            doc_idx = indexed_docs[name]
            for term in doc:
                term_idx = indexed_terms[term]
                tbd_matrix[term_idx, doc_idx] += 1

        return tbd_matrix

    def build_tbd_matrix(self) -> None:
        tbd_matrix = self._build_tbd()
        self._save_it(FT.tbd_matrix_not_norm, tbd_matrix)

        tbd_matrix = normalize(tbd_matrix, axis=0, copy=False)
        tbd_matrix = tbd_matrix.tocsc(copy=False)

        self._save_it(FT.tbd_matrix, tbd_matrix)
        print(
            f'saved term-by-document matrix at {self.paths[FT.tbd_matrix]}')

    def build_tbd_idf_matrix(self) -> None:
        tbd_idf_matrix = self._get_it(FT.tbd_matrix_not_norm)

        tbd_idf_matrix = tbd_idf_matrix.tocsr(copy=False)
        N = tbd_idf_matrix.shape[1]

        n_w_vec = scipy.sparse.linalg.norm(tbd_idf_matrix, ord=0, axis=1)
        idf_vec = np.log(N / n_w_vec)

        for i, idf in enumerate(idf_vec):
            tbd_idf_matrix[i, :] *= idf

        tbd_idf_matrix = normalize(tbd_idf_matrix, axis=0, copy=False)

        tbd_idf_matrix = tbd_idf_matrix.tocsc(copy=False)

        self._save_it(FT.tbd_idf_matrix, tbd_idf_matrix)

        print(
            f'saved term-by-document IDF matrix at {self.paths[FT.tbd_idf_matrix]}')

    def _build_svd(self, matrix, k, zero_tolerance=1e-13):
        U, S, VT = scipy.sparse.linalg.svds(matrix, k=k)
        D = np.diag(S)
        S = D @ VT

        S[abs(S) < zero_tolerance] = 0
        S = sparse.csc_matrix(S)
        S = normalize(S, axis=0, copy=False)

        return U, S

    def build_tbd_svd_matrix(self, k: int) -> None:
        tbd_svd_matrix = self._build_svd(
            self.get_tbd_matrix(), k)  # stored as tuple U, S

        # save it with _k as suffix
        k_path = f'{self.paths[FT.tbd_svd_matrix]}_{k}'

        save_binary(k_path, tbd_svd_matrix)
        self.files[FT.tbd_svd_matrix] = tbd_svd_matrix

        print(f'saved svd {k} low rank approx of tbd matrix at {k_path}')

    def build_tbd_idf_svd_matrix(self, k: int) -> None:
        tbd_idf_svd_matrix = self._build_svd(self.get_tbd_idf_matrix(), k)

        # save it with _k as suffix
        k_path = f'{self.paths[FT.tbd_idf_svd_matrix]}_{k}'

        save_binary(k_path, tbd_idf_svd_matrix)
        self.files[FT.tbd_idf_svd_matrix] = tbd_idf_svd_matrix

        print(f'saved svd {k} low rank approx of tbd idf matrix at {k_path}')

    def get_preprocessed_docs(self) -> Generator[Tuple[str, List[str]], None, None]:
        # throws FileNotFound if it wasn't preprocessed before
        # returns filename (urlencoded) with its preprocessed tokens
        has_files = False
        with os.scandir(self.paths[FT.preprocessed_data_dir]) as entries:
            for entry in entries:
                has_files = True
                with open(pathlib.Path(self.paths[FT.preprocessed_data_dir], entry.name), 'rb') as f:
                    yield entry.name, pickle.load(f)

        if not has_files:
            raise FileNotFoundError(
                f'no files found within {self.paths[FT.preprocessed_data_dir]}')

    def _get_it(self, file_type: FT) -> Any:
        if self.files[file_type] is not None:
            return self.files[file_type]

        self._load_it(file_type)
        return self.files[file_type]

    def get_doc_indices(self) -> Tuple[Dict[str, int], List[str]]:
        return self._get_it(FT.indexed_filenames_dict), self._get_it(FT.indexed_filenames_list)

    def get_indexed_terms(self) -> Dict[str, int]:
        return self._get_it(FT.indexed_terms)

    def get_tbd_matrix(self) -> "np.array":
        # returns normalized matrix
        return self._get_it(FT.tbd_matrix)

    def get_tbd_idf_matrix(self) -> "np.array":
        # returns normalized matrix with IDF already applied
        return self._get_it(FT.tbd_idf_matrix)

    def _get_svd(self, filetype: FT, k: int):
        if self.files[filetype] is not None and self.svd_orders[filetype] == k:
            return self.files[filetype]

        self.svd_orders[filetype] = k
        path = f'{self.paths[filetype]}_{k}'

        try:
            self.files[filetype] = load_binary(path)
            return self.files[filetype]
        except FileNotFoundError:
            available = []
            with os.scandir(self.PICKLE_DIR) as pd:
                for entry in pd:
                    if entry.name.startswith(filetype.value):
                        available.append(entry.name)

            msg = f'{k} low rank approx not found'
            msg += f' available: {available}' if len(available) > 0 else ''
            raise FileNotFoundError(msg)

    def get_tbd_svd_matrix(self, k: int):
        # returns normalized low rank approx using k singular values of tbd matrix
        return self._get_svd(FT.tbd_svd_matrix, k)

    def get_tbd_idf_svd_matrix(self, k: int):
        # returns normalized low rank approx using k singular values of tbd matrix with IDF already applied
        return self._get_svd(FT.tbd_idf_svd_matrix, k)

    def update_all(self) -> None:
        self.index_documents()
        self.preprocess_docs()
        self.index_terms()
        self.build_tbd_matrix()
        self.build_tbd_idf_matrix()

    def query2bag_of_words(self, query: str) -> "np.array":
        # returns normalized (M, 1) vector of terms
        # raises AttributeError if query doesn't contain any indexed terms
        tokens = self._preprocess_doc(query)
        indexed_terms = self.get_indexed_terms()
        M = len(indexed_terms)

        result = sparse.lil_matrix((M, 1))
        found = False
        for token in tokens:
            if token in indexed_terms:
                found = True
                result[indexed_terms[token], 0] += 1

        if not found:
            raise AttributeError(f'query: {query} contains no indexed terms')

        result /= scipy.sparse.linalg.norm(result)
        return result.tocsc(copy=False)

    def get_original_documents(self, idxs: List[int], max_len: int = 200) -> Generator[List[
            Tuple[str, str, str]], None, None]:
        _, indexed_docs = self.get_doc_indices()
        for idx in idxs:
            doc_name = indexed_docs[idx]
            raw_doc_path = pathlib.Path(self.RAW_DATA_DIR, doc_name)

            with open(raw_doc_path, 'r') as f:
                title = f.readline()
                content = f.read(np.random.randint(
                    max(max_len-80, 0), max_len))
                while(True):
                    letter = f.read(1)
                    if letter.isalnum():
                        content += letter
                    else:
                        break

            link = decode_url(doc_name)
            yield link, title, content

    def has_svd_of_order(self, k: int) -> bool:
        path = f'{self.paths[FT.tbd_svd_matrix]}_{k}'
        try:
            with open(path, 'r'):
                return True
        except FileNotFoundError:
            return False


def encode_url(url: str) -> str:
    return urllib.parse.quote(url, safe='')


def decode_url(filename: str) -> str:
    return urllib.parse.unquote(filename)


def save_binary(path: str, binary: Any) -> None:
    with open(path, 'wb') as f:
        pickle.dump(binary, f)


def load_binary(path: str) -> Any:
    with open(path, 'rb') as f:
        return pickle.load(f)
