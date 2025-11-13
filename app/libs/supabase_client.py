from supabase import create_client, Client
from app.libs.config import settings


class SupabaseClient:
    """Supabase client wrapper for database operations"""
    
    def __init__(self):
        self._client: Client = None
        self._service_client: Client = None
    
    @property
    def client(self) -> Client:
        """Get Supabase client with anon key (for user operations)"""
        if not self._client:
            self._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
        return self._client
    
    @property
    def service_client(self) -> Client:
        """Get Supabase client with service role key (for admin operations)"""
        if not self._service_client:
            self._service_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY
            )
        return self._service_client


# Global Supabase client instance
supabase_client = SupabaseClient()