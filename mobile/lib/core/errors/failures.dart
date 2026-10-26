/// Custom failure classes for error handling.
sealed class Failure {
  final String message;
  final int? statusCode;

  const Failure({required this.message, this.statusCode});

  @override
  String toString() => message;
}

class NetworkFailure extends Failure {
  const NetworkFailure({
    super.message = 'Network error. Check your connection.',
    super.statusCode,
  });
}

class ServerFailure extends Failure {
  const ServerFailure({required super.message, super.statusCode});
}

class AuthFailure extends Failure {
  const AuthFailure({required super.message, super.statusCode});
}

class ValidationFailure extends Failure {
  final Map<String, dynamic> errors;
  const ValidationFailure({
    required super.message,
    required this.errors,
    super.statusCode,
  });
}

class UnknownFailure extends Failure {
  const UnknownFailure({
    super.message = 'Something went wrong.',
    super.statusCode,
  });
}

/// A gym (tenant) option offered when the backend cannot disambiguate the
/// account's gym and asks the user to specify one to continue.
class GymOption {
  final String id;
  final String name;

  const GymOption({required this.id, required this.name});

  factory GymOption.fromJson(dynamic json) {
    if (json is Map) {
      return GymOption(
        id: (json['id'] ?? json['gym'] ?? json['value'] ?? '').toString(),
        name:
            (json['name'] ??
                    json['gym_name'] ??
                    json['label'] ??
                    json['id'] ??
                    json['gym'] ??
                    '')
                .toString(),
      );
    }
    // Bare id/value (int or string).
    final id = json.toString();
    return GymOption(id: id, name: id);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is GymOption && other.id == id;

  @override
  int get hashCode => id.hashCode;
}

/// The backend needs the user to specify their gym before sign-in can
/// complete ("specify your gym to continue" pattern).
class TenantSelectionRequiredFailure extends Failure {
  final List<GymOption> gyms;

  const TenantSelectionRequiredFailure({
    super.message = 'Specify your gym to continue',
    this.gyms = const [],
    super.statusCode,
  });
}
