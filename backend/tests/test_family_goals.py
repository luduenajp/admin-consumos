"""Tests for FamilyGoal CRUD and API endpoints."""
import pytest

from app.crud import create_family_goal, delete_family_goal, list_family_goals, update_family_goal
from app.schemas import FamilyGoalCreate, FamilyGoalUpdate


class TestFamilyGoalCRUD:
    def test_create_and_list(self, session):
        goal = create_family_goal(
            session=session,
            payload=FamilyGoalCreate(title="Vacaciones", target_amount=500000, priority="high"),
        )
        assert goal.id is not None
        assert goal.title == "Vacaciones"
        assert goal.target_amount == 500000
        assert goal.is_completed is False

        goals = list_family_goals(session=session)
        assert len(goals) == 1

    def test_create_minimal(self, session):
        goal = create_family_goal(session=session, payload=FamilyGoalCreate(title="Simple"))
        assert goal.title == "Simple"
        assert goal.target_amount is None
        assert goal.priority is None

    def test_update_fields(self, session):
        goal = create_family_goal(session=session, payload=FamilyGoalCreate(title="Sillón"))
        updated = update_family_goal(
            session=session,
            goal_id=goal.id,
            payload=FamilyGoalUpdate(target_amount=150000, priority="medium"),
        )
        assert updated.target_amount == 150000
        assert updated.priority == "medium"
        assert updated.title == "Sillón"  # unchanged

    def test_toggle_completed(self, session):
        goal = create_family_goal(session=session, payload=FamilyGoalCreate(title="Pintar casa"))
        assert goal.is_completed is False

        updated = update_family_goal(
            session=session, goal_id=goal.id, payload=FamilyGoalUpdate(is_completed=True)
        )
        assert updated.is_completed is True

        # Toggle back
        updated2 = update_family_goal(
            session=session, goal_id=goal.id, payload=FamilyGoalUpdate(is_completed=False)
        )
        assert updated2.is_completed is False

    def test_delete(self, session):
        goal = create_family_goal(session=session, payload=FamilyGoalCreate(title="Temporal"))
        delete_family_goal(session=session, goal_id=goal.id)
        goals = list_family_goals(session=session)
        assert len(goals) == 0

    def test_update_not_found(self, session):
        with pytest.raises(ValueError, match="not found"):
            update_family_goal(
                session=session, goal_id=9999, payload=FamilyGoalUpdate(title="X")
            )

    def test_delete_not_found(self, session):
        with pytest.raises(ValueError, match="not found"):
            delete_family_goal(session=session, goal_id=9999)

    def test_list_pending_before_completed(self, session):
        """Pending goals should appear before completed ones in listing."""
        g1 = create_family_goal(session=session, payload=FamilyGoalCreate(title="Pendiente"))
        g2 = create_family_goal(session=session, payload=FamilyGoalCreate(title="Hecho"))
        update_family_goal(session=session, goal_id=g2.id, payload=FamilyGoalUpdate(is_completed=True))

        goals = list_family_goals(session=session)
        assert goals[0].id == g1.id
        assert goals[1].id == g2.id


class TestFamilyGoalAPI:
    def test_create_goal_endpoint(self, client):
        resp = client.post("/api/goals", json={"title": "Viaje a Europa", "target_amount": 2000000})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Viaje a Europa"
        assert data["target_amount"] == 2000000
        assert data["is_completed"] is False

    def test_list_goals_endpoint(self, client):
        client.post("/api/goals", json={"title": "Meta 1"})
        client.post("/api/goals", json={"title": "Meta 2"})
        resp = client.get("/api/goals")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_goal_endpoint(self, client):
        resp = client.post("/api/goals", json={"title": "Objetivo"})
        goal_id = resp.json()["id"]

        resp = client.patch(f"/api/goals/{goal_id}", json={"is_completed": True, "notes": "Listo!"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_completed"] is True
        assert data["notes"] == "Listo!"

    def test_delete_goal_endpoint(self, client):
        resp = client.post("/api/goals", json={"title": "Borrar esto"})
        goal_id = resp.json()["id"]

        resp = client.delete(f"/api/goals/{goal_id}")
        assert resp.status_code == 204

        resp = client.get("/api/goals")
        assert len(resp.json()) == 0

    def test_create_missing_title(self, client):
        resp = client.post("/api/goals", json={"target_amount": 100})
        assert resp.status_code == 422

    def test_patch_not_found(self, client):
        resp = client.patch("/api/goals/9999", json={"title": "X"})
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/goals/9999")
        assert resp.status_code == 404
