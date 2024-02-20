from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import insert, select
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tests.models import (
    Category,
    CategorySchema,
    Child,
    Parent,
    ParentSchema,
    category_manager,
    child_manager,
    parent_manager,
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
    ), "Got not equal to object in database"

    nonexistent = await session.execute(
        select(Category).where(Category.title == "nonexistent-test-get-category-title")
    )
    assert nonexistent.scalars().first() is None, "Got nonexistent object"


async def test_get_with_options(session: AsyncSession):
    parent = Parent(
        id=uuid4(),
        title="test-parent-title",
        slug="test-parent-slug",
        description="test-parent-description",
    )
    child = Child(
        title="test-child-title",
        slug="test-child-slug",
        parent_id=parent.id,
    )
    session.add_all([parent, child])
    await session.commit()

    parent_without_options = await parent_manager.get(session=session)
    with pytest.raises(MissingGreenlet):
        assert len(parent_without_options.children) == 1
        assert parent_without_options.children[0].id == child.id

    parent_with_options = await parent_manager.get(
        session=session, id=parent.id, options=selectinload(Parent.children)
    )
    assert len(parent_with_options.children) == 1
    assert parent_with_options.children[0].id == child.id


async def test_get_with_order_by(session: AsyncSession):
    await session.execute(
        insert(Category),
        [
            {"title": "test-category-b"},
            {"title": "test-category-a"},
            {"title": "test-category-c"},
        ],
    )
    await session.commit()

    alphabetical_first_category = await category_manager.get(
        session=session, order_by=Category.title
    )
    assert alphabetical_first_category.title[-1] == "a"

    alphabetical_last_category = await category_manager.get(
        session=session, order_by=Category.title.desc()
    )
    assert alphabetical_last_category.title[-1] == "c"


async def test_get_with_where(session: AsyncSession):
    category_title = "test-category-title"
    category = Category(title=category_title)
    session.add(category)
    await session.commit()

    category_with_correct_where = await category_manager.get(
        session=session, where=(Category.title == category_title)
    )
    assert category_with_correct_where.title == category_title

    category_with_wrong_title = await category_manager.get(
        session=session, where=(Category.title == f"{category_title}-wrong")
    )
    assert category_with_wrong_title is None


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


async def test_exists_with_where(session: AsyncSession):
    category_title = "test-category-title"
    category = Category(title=category_title)
    session.add(category)
    await session.commit()

    category_exists = await category_manager.exists(
        session=session, where=(Category.title == category_title)
    )
    assert category_exists

    category_doesnt_exists = await category_manager.exists(
        session=session, where=(Category.title == f"nonexistent-{category_title}")
    )
    assert not category_doesnt_exists


async def test_get_or_404(session: AsyncSession):
    test_category = Category(title="test-category-title")
    session.add(test_category)
    await session.commit()

    category_from_manager = await category_manager.get_or_404(
        session=session, title="test-category-title"
    )
    category = await session.execute(
        select(Category).where(Category.title == "test-category-title")
    )
    assert category_from_manager == category.scalars().first()

    with pytest.raises(
        HTTPException,
        match="404: category with title=nonexistent-test-get-category-title not found",
    ):
        await category_manager.get_or_404(
            session=session, title="nonexistent-test-get-category-title"
        )


async def test_get_or_404_with_options(session: AsyncSession):
    parent = Parent(
        id=uuid4(),
        title="test-parent-title",
        slug="test-parent-slug",
        description="test-parent-description",
    )
    child = Child(
        title="test-child-title",
        slug="test-child-slug",
        parent_id=parent.id,
    )
    session.add_all([parent, child])
    await session.commit()

    parent_without_options = await parent_manager.get_or_404(session=session)
    with pytest.raises(MissingGreenlet):
        assert len(parent_without_options.children) == 1
        assert parent_without_options.children[0].id == child.id

    parent_with_options = await parent_manager.get_or_404(
        session=session, id=parent.id, options=selectinload(Parent.children)
    )
    assert len(parent_with_options.children) == 1
    assert parent_with_options.children[0].id == child.id


async def test_get_or_404_with_order_by(session: AsyncSession):
    await session.execute(
        insert(Category),
        [
            {"title": "test-category-b"},
            {"title": "test-category-a"},
            {"title": "test-category-c"},
        ],
    )
    await session.commit()

    alphabetical_first_category = await category_manager.get_or_404(
        session=session, order_by=Category.title
    )
    assert alphabetical_first_category.title[-1] == "a"

    alphabetical_last_category = await category_manager.get_or_404(
        session=session, order_by=Category.title.desc()
    )
    assert alphabetical_last_category.title[-1] == "c"


async def test_get_or_404_with_where(session: AsyncSession):
    category_title = "test-category-title"
    category = Category(title=category_title)
    session.add(category)
    await session.commit()

    category_with_correct_where = await category_manager.get_or_404(
        session=session, where=(Category.title == category_title)
    )
    assert category_with_correct_where.title == category_title

    with pytest.raises(
        HTTPException,
        match="404: category with , category.title = :title_1 not found",
    ):
        await category_manager.get_or_404(
            session=session, where=(Category.title == f"{category_title}-wrong")
        )


async def test_exists_or_404(session: AsyncSession):
    test_category = Category(title="test-category-title")
    session.add(test_category)
    await session.commit()

    category_from_manager = await category_manager.exists(
        session=session, title="test-category-title"
    )
    category = await session.execute(
        select(Category).where(Category.title == "test-category-title")
    )
    assert category_from_manager == (category.scalars().first() is not None)

    with pytest.raises(
        HTTPException,
        match="404: category with title=nonexistent-test-exists-category-title does not exist",
    ):
        await category_manager.exists_or_404(
            session=session, title="nonexistent-test-exists-category-title"
        )


async def test_exists_or_404_with_where(session: AsyncSession):
    category_title = "test-category-title"
    category = Category(title=category_title)
    session.add(category)
    await session.commit()

    category_exists = await category_manager.exists_or_404(
        session=session, where=(Category.title == category_title)
    )
    assert category_exists

    with pytest.raises(
        HTTPException,
        match="404: category with , category.title = :title_1 does not exist",
    ):
        await category_manager.exists_or_404(
            session=session, where=(Category.title == f"nonexistent-{category_title}")
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


async def test_create_unique_filed_validation(session: AsyncSession):
    await category_manager.create(
        session=session, in_obj=CategorySchema(title="test-create-category-title")
    )
    with pytest.raises(
        HTTPException,
        match="422: category c title test-create-category-title уже существует",
    ):
        await category_manager.create(
            session=session, title="test-create-category-title"
        )


async def test_create_without_commit(session: AsyncSession):
    category_title = "test-category-title"
    no_commit_category_title = f"{category_title}-no-commit"

    await category_manager.create(
        session=session, in_obj=CategorySchema(title=category_title), commit=True
    )
    await category_manager.create(
        session=session,
        in_obj=CategorySchema(title=no_commit_category_title),
        commit=False,
    )

    await session.close()

    async with session:
        category_to_check_without_commit = await session.execute(
            select(Category).where(Category.title == no_commit_category_title)
        )
        assert category_to_check_without_commit.scalars().first() is None

        category_to_check_with_commit = await session.execute(
            select(Category).where(Category.title == category_title)
        )
        assert category_to_check_with_commit.scalars().first().title == category_title


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


async def test_update_unique_filed_validation(session: AsyncSession):
    await session.execute(
        insert(Category),
        [{"title": "test-category-title1"}, {"title": "test-category-title2"}],
    )
    await session.commit()
    category_to_update = await session.execute(
        select(Category).where(Category.title == "test-category-title2")
    )
    with pytest.raises(
        HTTPException,
        match="422: category c title test-category-title1 уже существует",
    ):
        await category_manager.update(
            session=session,
            db_obj=category_to_update.scalars().first(),
            in_obj=CategorySchema(title="test-category-title1"),
        )


async def test_update_without_exclude_unset(session: AsyncSession):
    parent_title = "test-parent-title"
    parent_slug = "test-parent-slug"
    parent_description = "test-parent-description"
    parent = await parent_manager.create(
        session=session,
        in_obj=ParentSchema(
            title=parent_title,
            slug="test-parent-slug",
            description=parent_description,
        ),
        id=uuid4(),
    )
    assert parent.description == parent_description

    updated_parent = await parent_manager.update(
        session=session,
        db_obj=parent,
        in_obj=ParentSchema(title=f"{parent_title}-1", slug=parent_slug),
    )
    assert updated_parent.title == f"{parent_title}-1"
    assert updated_parent.description == parent_description

    updated_parent_without_exclude_unset = await parent_manager.update(
        session=session,
        db_obj=parent,
        in_obj=ParentSchema(title=f"{parent_title}-2", slug=parent_slug),
        exclude_unset=False,
    )
    assert updated_parent_without_exclude_unset.title == f"{parent_title}-2"
    assert updated_parent.description is None


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


async def count_with_where(session: AsyncSession):
    same_title = "test-count-category-title"
    await session.execute(
        insert(Parent),
        [
            {
                "title": same_title,
                "slug": "test-child-slug1",
                "description": "test-parent-description1",
            },
            {
                "title": same_title,
                "slug": "test-parent-slug2",
                "description": "test-parent-description2",
            },
            {
                "title": f"not-{same_title}",
                "slug": "test-parent-slug3",
                "description": "test-parent-description3",
            },
        ],
    )
    await session.commit()

    amount = await parent_manager.count(
        session=session, where=(Parent.title == same_title)
    )
    assert amount == 2, "Incorrect count result"


async def test_filter_with_where(session: AsyncSession):
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


async def test_filter_with_order_by(session: AsyncSession):
    same_title = "test-count-category-title"
    await session.execute(
        insert(Parent),
        [
            {
                "title": f"not-{same_title}",
                "slug": "test-parent-slug3",
                "description": "test-parent-description-b",
            },
            {
                "title": same_title,
                "slug": "test-parent-slug2",
                "description": "test-parent-description-c",
            },
            {
                "title": same_title,
                "slug": "test-child-slug1",
                "description": "test-parent-description-a",
            },
        ],
    )
    await session.commit()

    parents = await parent_manager.filter(
        session=session, title=same_title, order_by=Parent.description
    )
    assert len(parents) == 2
    assert parents[0].description[-1] == "a"
    assert parents[1].description[-1] == "c"


async def test_filter_with_options(session: AsyncSession):
    parent = Parent(
        id=uuid4(),
        title="test-parent-title-1",
        slug="test-parent-slug-1",
        description=None,
    )
    parent_without_children = Parent(
        id=uuid4(),
        title="test-parent-title-2",
        slug="test-parent-slug-2",
        description="test-parent-description-2",
    )
    child = Child(
        title="test-child-title",
        slug="test-child-slug",
        parent_id=parent.id,
    )
    session.add_all([parent, parent_without_children, child])
    await session.commit()

    parents_without_options = await parent_manager.filter(
        session=session, description=None
    )
    with pytest.raises(MissingGreenlet):
        assert parents_without_options[0].children[0].id == child.id

    parents_with_options = await parent_manager.filter(
        session=session,
        id=parent.id,
        options=selectinload(Parent.children),
        description=None,
    )
    assert len(parents_with_options) == 1
    assert parents_with_options[0].children[0].id == child.id


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


async def test_list_with_order_by(session: AsyncSession):
    await session.execute(
        insert(Parent),
        [
            {
                "title": "test-parent-title1",
                "slug": "test-parent-slug1",
                "description": "test-parent-description-b",
            },
            {
                "title": "test-parent-title2",
                "slug": "test-parent-slug2",
                "description": "test-parent-description-c",
            },
            {
                "title": "test-parent-title3",
                "slug": "test-child-slug3",
                "description": "test-parent-description-a",
            },
        ],
    )
    await session.commit()

    parents = await parent_manager.list(session=session, order_by=Parent.description)
    assert len(parents) == 3
    assert parents[0].description[-1] == "a"
    assert parents[-1].description[-1] == "c"


async def test_list_with_options(session: AsyncSession):
    parent = Parent(
        id=uuid4(),
        title="test-parent-title-1",
        slug="test-parent-slug-1",
        description="test-parent-description-1",
    )
    parent_without_children = Parent(
        id=uuid4(),
        title="test-parent-title-2",
        slug="test-parent-slug-2",
        description="test-parent-description-2",
    )
    child = Child(
        title="test-child-title",
        slug="test-child-slug",
        parent_id=parent.id,
    )
    session.add_all([parent, parent_without_children, child])
    await session.commit()

    parents_without_options = await parent_manager.list(session=session)
    with pytest.raises(MissingGreenlet):
        assert parents_without_options[0].children[0].id == child.id

    parents_with_options = await parent_manager.list(
        session=session,
        id=parent.id,
        options=selectinload(Parent.children),
    )
    assert len(parents_with_options) == 1
    assert parents_with_options[0].children[0].id == child.id


async def test_list_with_where(session: AsyncSession):
    same_title = "test-count-category-title"
    await session.execute(
        insert(Parent),
        [
            {
                "title": same_title,
                "slug": "test-child-slug1",
                "description": "test-parent-description1",
            },
            {
                "title": same_title,
                "slug": "test-parent-slug2",
                "description": "test-parent-description2",
            },
            {
                "title": f"not-{same_title}",
                "slug": "test-parent-slug3",
                "description": "test-parent-description3",
            },
        ],
    )
    await session.commit()

    parents = await parent_manager.list(
        session=session, where=(Parent.title == same_title)
    )
    assert len(parents) == 2, "Incorrect result amount"
    for parent in parents:
        assert parent.title == same_title


async def test_create_unique_constraint_validation(session: AsyncSession):
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


async def test_update_unique_constraint_validation(session: AsyncSession):
    await session.execute(
        insert(Parent),
        [
            {
                "title": "test-list-parent-title",
                "slug": "test-child-slug1",
                "description": "test-parent-description1",
            },
            {
                "title": "test-list-parent-title",
                "slug": "test-parent-slug2",
                "description": "test-parent-description2",
            },
        ],
    )
    await session.commit()
    parent_to_update = await session.execute(
        select(Parent).where(Parent.slug == "test-parent-slug2")
    )
    with pytest.raises(
        HTTPException, match="422: parent с такими title, description уже существует."
    ):
        await parent_manager.update(
            session=session,
            db_obj=parent_to_update.scalars().first(),
            in_obj=ParentSchema(
                title="test-list-parent-title",
                slug="test-parent-slug2",
                description="test-parent-description1",
            ),
        )


async def test_list_with_related_model_field_filter(session: AsyncSession):
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
                "title": "test-list-parent-title1",
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
    await session.commit()
    parents = await parent_manager.list(
        session=session, nullable_filter_expressions={Parent.description: "null"}
    )
    parents_list = await session.execute(
        select(Parent).where(Parent.description.is_(None))
    )

    assert len(parents) == 2
    assert parents == parents_list.scalars().all()
