from .preprocessor import Preprocessor
import numpy as np
import time
from enum import Enum
import threading


class Mode(Enum):
    TBD = 0
    TBD_IDF = 1
    SVD = 2
    SVD_IDF = 3


class SearchEngine:
    def __init__(self, k: int = 1000) -> None:
        self.preproc = Preprocessor()
        self.svd_mutex = threading.Lock()  # for updating low rank
        # of characters that will be sent (excluding title)
        self.max_doc_len = 250
        self.k = k
        self._init_preproc_data()
        self.zero_tolerance = 1e-3  # for counting matches
        self.computing_svd = False

    def _init_preproc_data(self) -> None:
        try:
            # if this file is missing everything else should be missing too
            self.preproc.get_doc_indices()
        except FileNotFoundError:
            print('Preprocessed files not found. Preprocessing all...')
            self.preproc.update_all()

        # self.preproc.build_tbd_matrix()
        # self.preproc.build_tbd_idf_matrix()
        # self.preproc.build_tbd_idf_svd_matrix(self.k)
        # self.preproc.build_tbd_svd_matrix(self.k)

        self.tbd_matrix = self.preproc.get_tbd_matrix()
        self.tbd_idf_matrix = self.preproc.get_tbd_idf_matrix()
        self._load_svds()

    def _load_svds(self):
        try:
            self.U, self.S = self.preproc.get_tbd_svd_matrix(self.k)
        except FileNotFoundError:
            print(f'TBD svd with k={self.k} not found. Building...')
            self.preproc.build_tbd_svd_matrix(self.k)
            self.U, self.S = self.preproc.get_tbd_svd_matrix(self.k)

        try:
            self.U_idf, self.S_idf = self.preproc.get_tbd_idf_svd_matrix(
                self.k)
        except FileNotFoundError:
            print(f'IDF svd with k={self.k} not found. Building...')
            self.preproc.build_tbd_idf_svd_matrix(self.k)
            self.U_idf, self.S_idf = self.preproc.get_tbd_idf_svd_matrix(
                self.k)

    def set_low_rank_order(self, k: int):
        self.svd_mutex.acquire()
        if self.computing_svd:
            self.svd_mutex.release()
            return
        self.computing_svd = True
        self.svd_mutex.release()

        print('loading......')
        print(k)
        self.k = k
        self._load_svds()
        print('done')

        self.svd_mutex.acquire()
        self.computing_svd = False
        self.svd_mutex.release()

    def has_svd_of_order(self, k: int):
        return self.preproc.has_svd_of_order(k)

    def get_svd_order(self):
        return self.k

    def _compute_results(self, q, mode):
        res = None

        if mode == Mode.TBD:
            res = q.T @ self.tbd_matrix
        elif mode == Mode.TBD_IDF:
            res = q.T @ self.tbd_idf_matrix

        if res is not None:
            return np.array(res.todense())

        if mode == Mode.SVD:
            return q.T @ self.U @ self.S

        return q.T @ self.U_idf @ self.S_idf

    def handle_query(self, query: str, offset: int = 0, k: int = 20, mode: Mode = Mode.SVD_IDF):
        start = time.time()
        q = self.preproc.query2bag_of_words(query)
        similarities = self._compute_results(q, mode)

        to_sort = [(i, similarity)
                   for i, similarity in enumerate(similarities[0])]
        to_sort.sort(key=lambda x: x[1], reverse=True)

        doc_idxs = [idx for idx, _ in to_sort[offset:offset+k]]

        links, titles, contents = zip(*list(
            self.preproc.get_original_documents(doc_idxs, self.max_doc_len)))
        correls = [sim for _, sim in to_sort[offset:offset+k]]

        time_taken = time.time() - start
        results = len([_ for _, sim in to_sort if sim > self.zero_tolerance])

        return {
            'links': links,
            'titles': titles,
            'contents': contents,
            'correlations': correls,
            'time': np.around(time_taken, 2),
            'results_count': results
        }


def main():
    se = SearchEngine()
    while True:
        query = input('enter query:\t')
        start = time.time()
        se.handle_query(query)
        end = time.time()
        print(f'got results in {np.around(end-start, 3)}s')
        print('------------------------------------------------------')


if __name__ == '__main__':
    main()
