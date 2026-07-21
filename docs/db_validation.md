# Database-Level Validation

The `create` and `update` methods perform validation on the passed values at the database level. Specifically:

## Foreign Keys Existence Validation

If `Child.parent_id` is a `ForeignKey` referencing `Parent.id`, and the value of `parent_id` is set via `child_manager.create` or `child_manager.update`, an SQL query will be executed to check the existence of a `Parent` with the provided ID.

If no such object exists, an `fastapi.HTTPException` will be raised.

## Many-to-Many Relationships Existence Validation

If `Post.tags` represents a `ManyToMany` relationship with `Tag.id`, and the `tags` value is set via `post_manager.create` or `post_manager.update` as a list of IDs, an SQL query will be executed to verify the existence of all `Tag` objects with the provided IDs.

If any of the objects do not exist, an `fastapi.HTTPException` will be raised.

## Unique Fields Validation

If `Post.slug` is a field defined with `unique=True`, and the value of `slug` is set via `post_manager.create` or `post_manager.update`, an SQL query will be executed to check that no other `Post` object exists with the same `slug` value.

If the uniqueness constraint is violated, an `fastapi.HTTPException` will be raised.

## Unique Constraints Validation

If the model defines unique constraints using `sqlalchemy.UniqueConstraint`, then when using the `create` or `update` methods, an SQL query will be executed to verify that no other objects with the same combination of field values in the unique constraint exist.

If the unique constraint is violated, an `fastapi.HTTPException` will be raised.

## Unique Indexes Validation

If the model defines a unique `sqlalchemy.Index`, then when using the `create` or `update` methods, an SQL query will be executed to verify that no other object violates that index.

For **partial** unique indexes (`postgresql_where=...`), validation runs only when the created/updated row itself matches the `WHERE` predicate. Rows outside the partial index are not checked against it.

Supported `postgresql_where` forms for deciding whether the row is covered:

- Column expressions such as `Model.kind == "main"` (including `and_(...)` of equalities)
- Simple `text()` equalities such as `text("kind = 'main'")`

Unsupported / complex predicates are treated as matching (fail-safe): validation still runs.