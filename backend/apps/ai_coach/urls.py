"""AI Coach URL configuration."""
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ChatView, ConversationMessagesView, AIConversationViewSet, AIRecommendationViewSet

router = DefaultRouter()
router.register(r"conversations", AIConversationViewSet, basename="ai-conversation")
router.register(r"recommendations", AIRecommendationViewSet, basename="ai-recommendation")

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path(
        "conversations/<int:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="ai-conversation-messages",
    ),
    *router.urls,
]
