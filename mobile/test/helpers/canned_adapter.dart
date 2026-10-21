import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// A recorded HTTP call — method, full URI, query parameters, and body.
class RecordedHttpCall {
  final String method;
  final Uri uri;
  final Object? body;

  const RecordedHttpCall(this.method, this.uri, this.body);

  Map<String, dynamic>? get bodyMap =>
      body is Map<String, dynamic> ? body as Map<String, dynamic> : null;
}

/// A tiny [HttpClientAdapter] that answers each request with a canned
/// response from a queue — no real network, no mocking framework.
///
/// A non-2xx status is surfaced the way Dio does it: the response is
/// rejected with a [DioException] carrying the status code, so the data
/// source's error mapping is exercised for real. Every request is recorded
/// into [recorded] so tests can assert on method, path, query, and payload.
class CannedAdapter implements HttpClientAdapter {
  CannedAdapter({
    List<Future<Response<dynamic>> Function()> calls = const [],
    this.throws,
  }) : _calls = List.of(calls);

  final List<Future<Response<dynamic>> Function()> _calls;
  final DioException Function()? throws;
  final List<RecordedHttpCall> recorded = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final callIndex = recorded.length;
    recorded.add(RecordedHttpCall(options.method, options.uri, options.data));
    final thrown = throws;
    if (thrown != null) throw thrown();
    final response = await _calls[callIndex]();
    final status = response.statusCode ?? 200;
    final body = jsonEncode(response.data);

    if (status >= 200 && status < 300) {
      return ResponseBody.fromString(
        body,
        status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }

    throw DioException(
      requestOptions: options,
      response: response,
      type: DioExceptionType.badResponse,
    );
  }

  @override
  void close({bool force = false}) {}
}

/// Builds a canned [Response] with the given status and JSON body.
Future<Response<dynamic>> cannedResponse(int status, Object? data) async {
  return Response<dynamic>(
    requestOptions: RequestOptions(path: '/'),
    statusCode: status,
    data: data,
  );
}