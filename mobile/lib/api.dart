import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class Api {
  Api({String? baseUrl})
      : baseUrl = baseUrl ??
            const String.fromEnvironment(
              'API_URL',
              defaultValue: 'http://10.0.2.2:5000/api/v1',
            );

  final String baseUrl;
  final storage = const FlutterSecureStorage();

  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    final token = await storage.read(key: 'token');
    final headers = <String, String>{
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
    final uri = Uri.parse('$baseUrl$path');
    final encoded = jsonEncode(body ?? <String, dynamic>{});
    late http.Response response;
    switch (method) {
      case 'POST':
        response = await http.post(uri, headers: headers, body: encoded);
        break;
      case 'PATCH':
        response = await http.patch(uri, headers: headers, body: encoded);
        break;
      case 'DELETE':
        response = await http.delete(uri, headers: headers);
        break;
      default:
        response = await http.get(uri, headers: headers);
    }
    dynamic data;
    if (response.body.isNotEmpty) data = jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(data is Map ? data['error'] ?? 'Request failed' : 'Request failed');
    }
    return data;
  }

  Future<void> login(String email, String password) async {
    final data = await request('/auth/login', method: 'POST', body: {
      'email': email.trim(),
      'password': password,
    });
    await storage.write(key: 'token', value: data['token']);
  }

  Future<void> register(Map<String, dynamic> details) async {
    final data = await request('/auth/register', method: 'POST', body: details);
    await storage.write(key: 'token', value: data['token']);
  }

  Future<void> logout() => storage.delete(key: 'token');
}
