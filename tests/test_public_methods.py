import pytest
from fastapi import HTTPException
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from fastapi_sqlalchemy_toolkit import NullableQuery
from tests.fixtures import (
    Category,
    CategorySchema,
    ChildSchema,
    ParentSchema,
    category_manager,
    child_manager,
    parent_manager,
    Child,
    Parent,
)


async def test_get(session: AsyncSession):
    category = Category(title="test-get-category-title")
    session.add(category)
    await session.commit()
    category = await category_manager.get(
        session=session, title="test-get-category-title"
    )
    category_to_check = await session.execute(
        select(Category).where(Category.title == "test-get-category-title")
    )
    assert (
        category == category_to_check.scalars().first()
    ), "Gotten not equal to object in database"

    nonexistent = await session.execute(
        select(Category).where(Category.title == "nonexistent-test-get-category-title")
    )
    assert nonexistent.scalars().first() is None, "Got nonexistent object"


async def test_exists(session: AsyncSession):
    category = Category(title="test-exists-category-title")
    session.add(category)
    await session.commit()
    category_exists = await category_manager.exists(
        session=session, title="test-exists-category-title"
    )
    assert category_exists, "Existing object not found"

    category_doesnt_exists = await category_manager.exists(
        session=session, title="nonexistent-test-exists-category-title"
    )
    assert not category_doesnt_exists, "Nonexistent object found"


async def test_get_or_404(session: AsyncSession):
    with pytest.raises(
        HTTPException,
        match="404: category with title=nonexistent-test-get-category-title not found",
    ):
        await category_manager.get_or_404(
            session=session, title="nonexistent-test-get-category-title"
        )


async def test_exists_or_404(session: AsyncSession):
    with pytest.raises(
        HTTPException,
        match="404: category with title=nonexistent-test-exists-category-title does not exist",
    ):
        await category_manager.exists_or_404(
            session=session, title="nonexistent-test-exists-category-title"
        )


async def test_create(session: AsyncSession):
    created = await category_manager.create(
        session=session, in_obj=CategorySchema(title="test-create-category-title")
    )
    category_to_check = await session.execute(
        select(Category).where(Category.title == "test-create-category-title")
    )
    assert (
        created == category_to_check.scalars().first()
    ), "Created not equal to object in database"

    with pytest.raises(
        HTTPException,
        match="422: category c title test-create-category-title уже существует",
    ):
        await category_manager.create(
            session=session, title="test-create-category-title"
        )


async def test_update(session: AsyncSession):
    category = Category(title="test-update-category-title")
    session.add(category)
    await session.commit()
    category = await category_manager.get(
        session=session, title="test-update-category-title"
    )
    updated = await category_manager.update(
        session=session,
        db_obj=category,
        in_obj=CategorySchema(title="UPDATED-test-update-category-title"),
    )
    category_to_check = await session.execute(
        select(Category).where(Category.title == "UPDATED-test-update-category-title")
    )
    assert (
        updated == category_to_check.scalars().first()
    ), "Updated not equal to object in database"


async def test_delete(session: AsyncSession):
    category = Category(title="test-delete-category-title")
    session.add(category)
    await session.commit()
    category = await category_manager.get(
        session=session, title="test-delete-category-title"
    )
    await category_manager.delete(
        session=session,
        db_obj=category,
    )
    category_to_check = await session.execute(
        select(Category).where(Category.title == "test-delete-category-title")
    )
    assert category_to_check.first() is None


async def test_count(session: AsyncSession):
    await session.execute(
        insert(Category),
        [
            {"title": "test-count-category-title1"},
            {"title": "test-count-category-title2"},
            {"title": "test-count-category-title3"},
        ],
    )
    await session.commit()
    amount = await category_manager.count(session=session)
    assert amount == 3, "Incorrect count result"


async def test_filter_with_simple_filter_expressions(session: AsyncSession):
    await session.execute(
        insert(Category),
        [
            {"title": "test-list-category-title1"},
            {"title": "test-list-category-title2"},
            {"title": "test-list-category-title3"},
        ],
    )
    await session.commit()

    category_list = await category_manager.filter(
        session=session,
        where=(
            Category.title.in_(
                ["test-list-category-title1", "test-list-category-title2"]
            )
        ),
    )
    categories = await session.execute(
        select(Category).where(
            Category.title.in_(
                ["test-list-category-title1", "test-list-category-title2"]
            )
        )
    )

    assert len(category_list) == 2
    assert category_list == categories.scalars().all()


async def test_filter_with_simple_filter(session: AsyncSession):
    await session.execute(
        insert(Category),
        [
            {"title": "test-list-category-title1"},
            {"title": "test-list-category-title2"},
            {"title": "test-list-category-title3"},
        ],
    )
    await session.commit()

    category_list = await category_manager.filter(
        session=session, title="test-list-category-title1"
    )
    categories = await session.execute(
        select(Category).where(Category.title == "test-list-category-title1")
    )

    assert len(category_list) == 1
    assert category_list == categories.scalars().all()


async def test_list_with_simple_filter_expressions(session: AsyncSession):
    await session.execute(
        insert(Category),
        [
            {"title": "test-list-category-title1"},
            {"title": "test-list-category-title2"},
            {"title": "test-list-category-title3"},
        ],
    )
    await session.commit()

    category_list = await category_manager.list(
        session=session,
        filter_expressions={
            Category.title.in_: [
                "test-list-category-title1",
                "test-list-category-title2",
            ]
        },
    )
    categories = await session.execute(
        select(Category).where(
            Category.title.in_(
                ["test-list-category-title1", "test-list-category-title2"]
            )
        )
    )

    assert len(category_list) == 2
    assert category_list == categories.scalars().all()


async def test_list_with_simple_filter(session: AsyncSession):
    await session.execute(
        insert(Category),
        [
            {"title": "test-list-category-title1"},
            {"title": "test-list-category-title2"},
            {"title": "test-list-category-title3"},
        ],
    )
    await session.commit()

    category_list = await category_manager.list(
        session=session, title="test-list-category-title1"
    )
    categories = await session.execute(
        select(Category).where(Category.title == "test-list-category-title1")
    )

    assert len(category_list) == 1
    assert category_list == categories.scalars().all()


async def test_unique_constraint_validation(session: AsyncSession):
    await parent_manager.create(
        session=session,
        in_obj=ParentSchema(
            title="test-parent-title",
            slug="test-parent-slug1",
            description="test-parent-description",
        ),
    )
    with pytest.raises(
        HTTPException, match="422: parent с такими title, description уже существует."
    ):
        await parent_manager.create(
            session=session,
            in_obj=ParentSchema(
                title="test-parent-title",
                slug="test-parent-slug2",
                description="test-parent-description",
            ),
        )


async def test_list_with_fk_filter(session: AsyncSession):
    first_parent_id = uuid4()
    second_parent_id = uuid4()
    await parent_manager.create(
        session=session,
        in_obj=ParentSchema(
            title="test-parent-title",
            slug="test-parent-slug1",
            description="test-parent-description1",
        ),
        id=first_parent_id,
    )
    await parent_manager.create(
        session=session,
        in_obj=ParentSchema(
            title="test-parent-title",
            slug="test-parent-slug2",
            description="test-parent-description2",
        ),
        id=second_parent_id,
    )
    await session.execute(
        insert(Child),
        [
            {
                "title": "test-list-child-title1",
                "slug": "test-child-slug1",
                "parent_id": first_parent_id,
            },
            {
                "title": "test-list-child-title2",
                "slug": "test-child-slug2",
                "parent_id": first_parent_id,
            },
            {
                "title": "test-list-child-title3",
                "slug": "test-child-slug3",
                "parent_id": second_parent_id,
            },
        ],
    )
    await session.commit()

    children_list = await child_manager.list(
        session=session,
        filter_expressions={Parent.slug: "test-parent-slug1"},
    )
    children = await session.execute(
        select(Child).join(Parent).where(Parent.slug == "test-parent-slug1")
    )

    assert len(children_list) == 2
    assert children_list == children.scalars().all()


async def test_null_filtration(session: AsyncSession):
    await session.execute(
        insert(Parent),
        [
            {
                "title": "test-list-child-title1",
                "slug": "test-child-slug1",
                "description": "test-parent-description",
            },
            {
                "title": "test-list-parent-title2",
                "slug": "test-parent-slug2",
            },
            {
                "title": "test-list-parent-title3",
                "slug": "test-parent-slug3",
            },
        ],
    )
    parents = await parent_manager.list(
        session=session, nullable_filter_expressions={Parent.description: "null"}
    )
    parents_list = await session.execute(
        select(Parent).where(Parent.description.is_(None))
    )

    assert len(parents) == 2
    assert parents == parents_list.scalars().all()
