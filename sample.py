from flask_sqlalchemy import DefaultMeta
from flask_platform_components import db

class BaseModelMetaClass(DefaultMeta):
    def __new__(BaseModelMetaClass, name, bases, classdict):

        return super().__new__(BaseModelMetaClass, name, bases, classdict)

    def __init__(cls, name, bases, classdict):
        # Check if 'autogenerate_relationships' attribute is in __dict__
        # the attribute must belong to the class not to the parent, because each meta will handle its own attribute
        # if True: create the autogenerate_relationships corresponding
        if 'autogenerate_relationships' in cls.__dict__ and cls.autogenerate_relationships is not None:
            # the attribute must be setted as following
            # autogenerate_relationships = dict(
            #     [ many_to_one | one_to_one | many_to_many ]=dict(
            #         <attribute_name>=dict(
            #             model=<model_class>,
            #             backref=<backref_attribute>,
            #             ...
            #         )
            #     )
            # )
            for relatiobship_type, value in cls.autogenerate_relationships.items():

                if relatiobship_type == "one_to_one":

                    for attribute_name, elements in value.items():
                        attibute_args=dict(elements)
                        model = attibute_args.pop('model')
                        backref = attibute_args.pop('backref', None)
                        # the foreign key take the attribute name with suffix _id, and the attribute_name is kept for the relationship attr
                        setattr(
                            cls,
                            attribute_name+"_id",
                            db.Column(model.id.name, db.Integer(), db.ForeignKey(model.__tablename__+"."+model.id.name), **attibute_args)
                        )
                        if backref:
                            setattr(
                                cls,
                                attribute_name,
                                db.relationship(model.__name__, backref=db.backref(backref, uselist=False, lazy="immediate", cascade="all, delete-orphan"))
                            )
                        else:
                            setattr(cls, attribute_name, db.relationship(model.__name__))

                elif relatiobship_type == "many_to_one":
                    for attribute_name, elements in value.items():
                        attibute_args=dict(elements)
                        model = attibute_args.pop('model')
                        backref = attibute_args.pop('backref', None)
                        setattr(
                            cls,
                            attribute_name + "_id",
                            # the column name must take the name of the column to which it points as a prefix
                            db.Column(model.id.name+'__'+attribute_name, db.Integer(), db.ForeignKey(model.__tablename__ + "."+model.id.name), **attibute_args)
                        )
                        if backref:
                            setattr(
                                cls,
                                attribute_name,
                                db.relationship(model.__name__,
                                                backref=db.backref(backref, lazy='dynamic', cascade="all, delete-orphan"),
                                                #precise the foreignkey to handle multiple attributes pointing the same model
                                                foreign_keys=[getattr(cls, attribute_name + "_id")]
                                                )
                            )
                        else:
                            setattr(
                                cls,
                                attribute_name,
                                db.relationship(model.__name__, foreign_keys=[getattr(cls, attribute_name + "_id")])
                            )
                elif relatiobship_type == "many_to_many":
                    for attribute_name, elements in value.items():
                        attibute_args=dict(elements)
                        model = attibute_args.pop('model')
                        backref = attibute_args.pop('backref', None)
                        # relation between cls and attibute_args so :
                        relation_table = db.Table(
                            "{}_{}_table".format(attribute_name, backref or ''),
                            db.Column(
                                cls.id.name, db.Integer(), db.ForeignKey(cls.__tablename__ + "."+cls.id.name),
                                primary_key=True
                            ),
                            db.Column(
                                model.id.name, db.Integer(), db.ForeignKey(model.__tablename__ + "."+model.id.name),
                                primary_key=True
                            )
                        )
                        # relation table must be stored in the class in case of we need it
                        setattr(cls, attribute_name+"_table", relation_table)
                        if backref:
                            setattr(cls, attribute_name, db.relationship(model.__name__, secondary=relation_table,
                                                           backref=db.backref(backref, lazy='dynamic'), **attibute_args))
                        else:
                            setattr(cls, attribute_name, db.relationship(model.__name__, secondary=relation_table, **attibute_args))

        # we init the class
        super(BaseModelMetaClass, cls).__init__(name, bases, classdict)
        base_classes = [element.__name__ for element in cls.__mro__]
        # TODO: handle depth inheritance when creating Delete classes
        #   because some time we have a Model that inherit for another Model and the second model inherit form
        #   DeleteModelMixin
        # if delete model mixin is in its base class, we need to create a model
        if 'DeleteModelMixin' in base_classes:
            class DeletedClass(BaseModel):
                pass
            cls.deleted_model_class = DeletedClass
            #RENAME THE CLASS DYNAMICALLY
            DeletedClass.__name__ = '{}AfterDeleted'.format(cls.__name__)

        if 'SalableItemMixin' in base_classes or 'SalableItemRecurrentMixin' in base_classes:
            #add the class to SALABLE ITEM CLASSES so buyers can purchase it
            from flask_platform_purchase import SALABLE_ITEM_CLASSES
            if cls.__name__ in SALABLE_ITEM_CLASSES.keys():
                # Should never be raise
                raise Exception('This "{}" salable is already registered.'.format(cls.__name__))
            SALABLE_ITEM_CLASSES[cls.__name__] = cls