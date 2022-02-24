from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .search_engine import SearchEngine, Mode
import json
import threading

se = SearchEngine(k=1000)


def main(request):
    return render(request, 'svd/index.html')


class SearchQuery(APIView):
    QUERY_PARAM_NAME = 'q'
    OFFSET_PARAM_NAME = 'offset'
    MODE_PARAM_NAME = 'mode'

    def get(self, request):
        query = request.GET.get(self.QUERY_PARAM_NAME)
        offset = int(request.GET.get(self.OFFSET_PARAM_NAME)) or 0
        m = request.GET.get(self.MODE_PARAM_NAME)
        if m is None:
            m = 3
        m = int(m)
        if m < 0 or m > 3:
            return Response({'error': f'Mode has to be in range [0, 3], got ${m}'},
                            status=status.status.HTTP_400_BAD_REQUEST)

        mode = Mode(m)

        if query is None:
            return Response({'error': f'Expected query parameter "{self.PARAM_NAME}"'},
                            status=status.status.HTTP_400_BAD_REQUEST)
        try:
            response = se.handle_query(query, offset=offset, k=200, mode=mode)
            response = json.dumps(response)
            return Response(response, status=status.HTTP_200_OK)
        except AttributeError:
            return Response({'error': f'Failed to find any articles containing one of words from: ${query}'},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SettingsQuery(APIView):
    ORDER_NAME = 'order'

    def put(self, request):
        try:
            k = request.data[self.ORDER_NAME]
        except KeyError:
            return Response({'error': f'Expected key "mode" in request body'},
                            status=status.HTTP_400_BAD_REQUEST)

        already_comptd = se.has_svd_of_order(k)
        threading.Thread(target=se.set_low_rank_order, args=(k,)).start()
        return Response({'computed': already_comptd}, status=status.HTTP_200_OK)

    def get(self, request):
        k = se.get_svd_order()
        return Response({'k': k}, status=status.HTTP_200_OK)
