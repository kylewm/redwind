alter table post add column updated timestamp;
update post set updated=published where updated is null;
