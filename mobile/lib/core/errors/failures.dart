/// Custom failure classes for error handling.
sealed class Failure {
  final String message;
  final int? statusCode;

  const Failure({required this.message, this.statusCode});

  @override
  String toString() => message;
}

class NetworkFailure extends Failure {
  const NetworkFailure({super.message = 'Network error. Check your connection.', super.statusCode});
}

class ServerFailure extends Failure {
  const ServerFailure({required super.message, super.statusCode});
}

class AuthFailure extends Failure {
  const AuthFailure({required super.message, super.statusCode});
}

class ValidationFailure extends Failure {
  final Map<String, dynamic> errors;
  const ValidationFailure({required super.message, required this.errors, super.statusCode});
}

class UnknownFailure extends Failure {
  const UnknownFailure({super.message = 'Something went wrong.', super.statusCode});
}