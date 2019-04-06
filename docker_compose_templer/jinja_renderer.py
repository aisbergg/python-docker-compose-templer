import os
from ast import literal_eval
from copy import deepcopy
from distutils.util import strtobool
from hashlib import sha1

import jinja2
import ruamel.yaml as yaml

from docker_compose_templer import jinja_filter
from docker_compose_templer.utils import merge_dicts


class JinjaRenderer(object):
    """Supplies functions to render templates with Jinja.

    Attributes:
        omit_placeholder (str): The omit placeholder used for removing keys from a dict/yaml
        env: The jinja environment used to render strings

    """

    omit_placeholder = '__omit_place_holder__%s' % sha1(os.urandom(64)).hexdigest()
    env = jinja2.Environment(
        lstrip_blocks=True,
        trim_blocks=True,
        undefined=jinja2.StrictUndefined
    )
    env.filters = merge_dicts(env.filters, jinja_filter.filters)

    @staticmethod
    def _evaluate_string(string):
        """Evaluates a string containing a Python value.

        Args:
            string(str): A Python value represented as a string

        Returns:
            str, int, float, bool, list or dict: The value of the evaluated string
        """
        try:
            # evaluate to int, float, list, dict
            return literal_eval(string.strip())
        except (ValueError, SyntaxError) as e:
            try:
                # evaluate bool from different variations
                return bool(strtobool(string.strip()))
            except ValueError as e:
                # string cannot be evaluated -> return string
                return string

    class Omit(object):
        """Represents a omit object"""
        pass

    @classmethod
    def render_string(cls, template_string, context):
        """Renders a template string with Jinja.

        Args:
            template_string (str): The template string to be rendered
            context (dict): The context used for rendering

        Returns:
            str: The rendered string

        Raises:
            jinja_filter.MandatoryError: If a variable is undefined and the mandatory filter was used
            jinja2.UndefinedError: If a variable is undefined
            jinja2.TemplateError: If the template contains an invalid syntax
        """
        # add omit variable to context
        context['omit'] = JinjaRenderer.omit_placeholder

        try:
            return cls.env.from_string(template_string).render(context)
        except jinja_filter.MandatoryError as e:
            raise e
        except jinja2.UndefinedError as e:
            raise jinja2.UndefinedError('Undefined variable: {0}'.format(str(e.message)))
        except jinja2.TemplateError as e:
            raise jinja2.TemplateError('Jinja template error: {0}'.format(str(e.message)))

    @classmethod
    def render_dict_and_add_to_context(cls, the_dict, context):
        """Renders a dict and adds it to the context.

        Args:
            the_dict (dict): The dict to be rendered
            context (dict): The context that is used for rendering

        Returns:
            dict: The context that contains also the variables from the_dict

        Raises:
            jinja_filter.MandatoryError: If a variable is undefined and the mandatory filter was used
            jinja2.UndefinedError: If a variable is undefined
            jinja2.TemplateError: If the template contains an invalid syntax
        """
        new_context = deepcopy(context)
        for k, v in the_dict.items():
            processed_value = cls._render_recursively(v, new_context)
            if type(processed_value) is not JinjaRenderer.Omit:
                new_context = merge_dicts(new_context, {k: processed_value})
        return new_context

    @classmethod
    def _render_recursively(cls, value, context):
        """Renders a value recursively.

        Args:
            value: Value to be rendered
            context: The context used for rendering

        Returns:
            Value that has been rendered with Jinja

        Raises:
            jinja_filter.MandatoryError: If a variable is undefined and the mandatory filter was used
            jinja2.UndefinedError: If a variable is undefined
            jinja2.TemplateError: If the template contains an invalid syntax
        """
        if value is None:
            return None

        # str
        elif type(value) is str:
            rendered_value = cls.render_string(value, context)
            if rendered_value == value:
                return value
            else:
                if rendered_value.find(JinjaRenderer.omit_placeholder) != -1:
                    return JinjaRenderer.Omit()
                else:
                    return cls._evaluate_string(rendered_value)

        # lists
        elif type(value) is list:
            new_list = []
            for li in value:
                processed_item = cls._render_recursively(li, context)
                if type(processed_item) is not JinjaRenderer.Omit:
                    new_list.append(processed_item)
            return new_list

        # dicts
        elif type(value) is dict:
            new_dict = {}
            for k, v in value.items():
                processed_value = cls._render_recursively(v, context)
                if type(processed_value) is not JinjaRenderer.Omit:
                    new_dict[k] = processed_value
            return new_dict

        # other types
        else:
            return value

    @classmethod
    def remove_omit_from_dict(cls, value):
        """Parses a YAML string and produce the corresponding Python object.

        Args:
            value: The value from which all occurrences of omit shall be removed

        Returns:
            dict: The processed dict
        """
        if value is None:
            return None

        elif type(value) is str:
            if value.find(JinjaRenderer.omit_placeholder) != -1:
                return JinjaRenderer.Omit()
            else:
                return value

        # lists
        elif isinstance(value, (yaml.comments.CommentedSeq, list)):
            vlen = len(value)
            for i in range(vlen - 1, -1, -1):
                processed_item = cls.remove_omit_from_dict(value[i])
                if type(processed_item) is JinjaRenderer.Omit:
                    del value[i]
                    i -= 1
            return value

        # dicts
        elif isinstance(value, (yaml.comments.CommentedMap, dict)):
            for key in list(value.keys()):
                processed_value = cls.remove_omit_from_dict(value[key])
                if type(processed_value) is JinjaRenderer.Omit:
                    del value[key]
            return value

        else:
            return value
