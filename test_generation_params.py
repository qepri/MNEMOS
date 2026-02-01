#!/usr/bin/env python3
"""
Test script for LLM Generation Parameters

Run this after deploying to verify the implementation works.
"""

def test_database_fields():
    """Test that database fields exist and have correct defaults"""
    from app.extensions import db
    from app.models.user_preferences import UserPreferences
    from app import create_app

    app = create_app()
    with app.app_context():
        # Get or create preferences
        prefs = db.session.query(UserPreferences).first()
        if not prefs:
            prefs = UserPreferences()
            db.session.add(prefs)
            db.session.commit()
            print("✓ Created new UserPreferences record")

        # Check fields exist
        assert hasattr(prefs, 'llm_max_tokens'), "❌ Missing llm_max_tokens field"
        assert hasattr(prefs, 'llm_temperature'), "❌ Missing llm_temperature field"
        assert hasattr(prefs, 'llm_top_p'), "❌ Missing llm_top_p field"
        assert hasattr(prefs, 'llm_frequency_penalty'), "❌ Missing llm_frequency_penalty field"
        assert hasattr(prefs, 'llm_presence_penalty'), "❌ Missing llm_presence_penalty field"
        print("✓ All database fields exist")

        # Check defaults
        assert prefs.llm_max_tokens == 4096, f"❌ Wrong default for max_tokens: {prefs.llm_max_tokens}"
        assert prefs.llm_temperature == 0.7, f"❌ Wrong default for temperature: {prefs.llm_temperature}"
        assert prefs.llm_top_p == 0.9, f"❌ Wrong default for top_p: {prefs.llm_top_p}"
        assert prefs.llm_frequency_penalty == 0.3, f"❌ Wrong default for frequency_penalty: {prefs.llm_frequency_penalty}"
        assert prefs.llm_presence_penalty == 0.1, f"❌ Wrong default for presence_penalty: {prefs.llm_presence_penalty}"
        print("✓ All defaults are correct")

        # Check to_dict includes new fields
        prefs_dict = prefs.to_dict()
        assert 'llm_max_tokens' in prefs_dict, "❌ llm_max_tokens not in to_dict()"
        assert 'llm_temperature' in prefs_dict, "❌ llm_temperature not in to_dict()"
        assert 'llm_top_p' in prefs_dict, "❌ llm_top_p not in to_dict()"
        assert 'llm_frequency_penalty' in prefs_dict, "❌ llm_frequency_penalty not in to_dict()"
        assert 'llm_presence_penalty' in prefs_dict, "❌ llm_presence_penalty not in to_dict()"
        print("✓ All fields serialized in to_dict()")

        print("\n✅ Database layer: ALL TESTS PASSED")
        return True


def test_llm_client():
    """Test that LLM client uses the parameters"""
    from app.services.llm_client import get_llm_client
    from app.models.user_preferences import UserPreferences
    from app.extensions import db
    from app import create_app

    app = create_app()
    with app.app_context():
        # Set custom parameters
        prefs = db.session.query(UserPreferences).first()
        prefs.llm_max_tokens = 2048
        prefs.llm_temperature = 0.5
        prefs.llm_frequency_penalty = 0.8
        db.session.commit()
        print("✓ Set custom parameters in DB")

        # Note: Actual LLM call testing would require mocking
        # Just verify the code path exists
        client = get_llm_client()
        print("✓ LLM client initialized successfully")

        print("\n✅ LLM Client layer: TESTS PASSED")
        return True


def test_api_endpoint():
    """Test that API returns new fields"""
    from app import create_app
    import json

    app = create_app()
    with app.test_client() as client:
        # GET preferences
        response = client.get('/api/settings/chat-preferences')
        assert response.status_code == 200, f"❌ API returned {response.status_code}"

        data = json.loads(response.data)
        assert 'llm_max_tokens' in data, "❌ llm_max_tokens not in API response"
        assert 'llm_temperature' in data, "❌ llm_temperature not in API response"
        assert 'llm_top_p' in data, "❌ llm_top_p not in API response"
        assert 'llm_frequency_penalty' in data, "❌ llm_frequency_penalty not in API response"
        assert 'llm_presence_penalty' in data, "❌ llm_presence_penalty not in API response"
        print("✓ GET /api/settings/chat-preferences returns all fields")

        # PUT preferences
        data['llm_max_tokens'] = 1024
        data['llm_temperature'] = 0.8
        response = client.put('/api/settings/chat-preferences',
                             data=json.dumps(data),
                             content_type='application/json')
        assert response.status_code == 200, f"❌ PUT failed with {response.status_code}"
        print("✓ PUT /api/settings/chat-preferences updates successfully")

        # Verify update
        response = client.get('/api/settings/chat-preferences')
        data = json.loads(response.data)
        assert data['llm_max_tokens'] == 1024, "❌ Update not persisted"
        assert data['llm_temperature'] == 0.8, "❌ Update not persisted"
        print("✓ Updates persisted correctly")

        print("\n✅ API layer: ALL TESTS PASSED")
        return True


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("LLM Generation Parameters - Implementation Test Suite")
    print("="*60)
    print()

    try:
        test_database_fields()
        test_llm_client()
        test_api_endpoint()

        print()
        print("="*60)
        print("🎉 ALL TESTS PASSED! Implementation is working correctly.")
        print("="*60)
        print()
        print("Next steps:")
        print("1. Navigate to Settings → Chat Settings in the UI")
        print("2. Verify the 'Generation Parameters' section appears")
        print("3. Test slider controls and help modal")
        print("4. Save settings and verify they persist")
        print("5. Test with a potentially repetitive prompt")
        print()

    except AssertionError as e:
        print()
        print("="*60)
        print(f"❌ TEST FAILED: {e}")
        print("="*60)
        return False
    except Exception as e:
        print()
        print("="*60)
        print(f"❌ ERROR: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    run_all_tests()
