"""AI Coach views — FBOS-017."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication

from .models import AIConversation, AIMessage, AIRecommendation
from .serializers import (
    AIConversationSerializer,
    AIMessageSerializer,
    AIRecommendationSerializer,
    ChatRequestSerializer,
)
from .services.ai_service import generate_response


class AIConversationViewSet(ModelViewSet):
    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]
    serializer_class = AIConversationSerializer

    def get_queryset(self):
        return AIConversation.objects.filter(tenant_id=self.request.user.tenant_id, user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.user.tenant_id, user=self.request.user)


class ChatView(APIView):
    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "ai_coach.use_ai_coach"

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        conversation_id = data.get("conversation_id")
        if conversation_id:
            conversation = AIConversation.objects.get(id=conversation_id, user=request.user)
        else:
            conversation = AIConversation.objects.create(
                tenant_id=request.user.tenant_id,
                user=request.user,
                title=data["message"][:50],
            )
        AIMessage.objects.create(conversation=conversation, role="user", content=data["message"])
        response_text, recommendation_data = generate_response(data["message"], request.user, conversation)
        AIMessage.objects.create(conversation=conversation, role="assistant", content=response_text)
        recommendation = None
        if recommendation_data:
            rec = AIRecommendation.objects.create(
                tenant_id=request.user.tenant_id,
                user=request.user,
                conversation=conversation,
                type=recommendation_data["type"],
                content=recommendation_data["content"],
            )
            recommendation = {"id": rec.id, "type": rec.type, "content": rec.content}
        return Response(
            {
                "response": response_text,
                "conversation_id": conversation.id,
                "recommendation": recommendation,
            },
            status=status.HTTP_200_OK,
        )


class ConversationMessagesView(APIView):
    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request, conversation_id):
        conversation = AIConversation.objects.filter(id=conversation_id, user=request.user).first()
        if conversation is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        messages = AIMessage.objects.filter(conversation=conversation)
        return Response(AIMessageSerializer(messages, many=True).data)


class AIRecommendationViewSet(ModelViewSet):
    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]
    serializer_class = AIRecommendationSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        return AIRecommendation.objects.filter(tenant_id=self.request.user.tenant_id, user=self.request.user)
