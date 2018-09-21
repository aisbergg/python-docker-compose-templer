# Docker Compose Templer

This little Python 3 program adds more dynamics to [Docker Compose or Docker Stack files](https://docs.docker.com/compose/compose-file/) by utilizing the [Jinja2 template engine](http://jinja.pocoo.org/).

Docker Compose (DC) files allow [variable substitution](https://docs.docker.com/compose/compose-file/#variable-substitution) with environment variables. This functionality offers very simple dynamics that can be used for customizing specific options of the DC file during startup. When a single DC file shall be used to create different service instances with varying environment variables, networks, volumes, etc., the simple method of variable substitution is not convenient. Therefore I decided to create this Python program to introduce templating with Jinja2 to DC files. A definition file says where to find the templates, what variables to use for rendering and where to put the resulting files.

The documentation of Jinja2 can be found [here](http://jinja.pocoo.org/docs/dev/templates/).

**Features:**

* templating using Jinja2
* using some [extra Jinja filters](#extra-jinja2-filters) (comply with Ansible filters)
* monitoring of file changes and automatic rendering of templates (especially useful during development)
* using YAML syntax for definition and variable files

**Table of contents:**
<!-- TOC depthFrom:2 depthTo:6 withLinks:1 updateOnSave:0 orderedList:0 -->

- [Installation](#installation)
- [Usage](#usage)
	- [Command line arguments](#command-line-arguments)
	- [Definition File](#definition-file)
	- [Templates](#templates)
	- [Examples](#examples)
- [Extra Jinja2 Filters](#extra-jinja2-filters)
- [License](#license)

<!-- /TOC -->

---

## Installation

Install directly from Github:
```
pip install git+https://github.com/Aisbergg/python-docker-compose-templer@v1.0.1
```

Install from PyPi:
```
pip install docker-compose-templer
```

## Usage
### Command line arguments

```
usage: docker_compose_templer [-a] [-f] [-h] [-v] [--version]
                              definition_file [definition_file ...]

Render Docker Compose file templates with the power of Jinja2

positional arguments:
  definition_file    File that defines what to do.

optional arguments:
  -a, --auto-render  Monitor file changes and render templates automatically
  -f, --force        Overwrite existing files
  -h, --help         Show this help message and exit
  -v, --verbose      Enable verbose mode
  --version          Print the program version and quit
```

### Definition File

The definition file defines what to do. It lists template and the variables to be used for rendering and says where to put the resulting file. The definition file syntax is as follows:

```yaml
# define global variables to be used in all templates - can contain Jinja syntax
vars:
  some_global_var: foo
  another_global_var: "{{some_global_var}}bar" # will render to 'foobar'

# load global variables from YAML file(s) (order matters) - can contain Jinja syntax
include_vars:
  - path/to/file_1.yml
  - path/to/file_2.yml

# template definitions
templates:
  # first template
  - src: templates/my_template.yml.j2 # source file as Jinja2 template (Jinja syntax can be used on path)
    dest: stacks/s1/my_instance.yml   # path for resulting file (Jinja syntax can be used on path)
    include_vars: variables/s1.yml  # include local variables from YAML file(s)
    vars:                           # local variables for this template
      some_local_var: abc

  # second template
  - src: templates/my_template.yml.j2
    dest: stacks/s2/my_instance.yml
    vars:
      some_local_var: xyz
```

The variables can itself contain Jinja syntax, you only have to make sure the variables are defined prior usage. The different sources of variables are merged together in the following order:

1. global `include_vars`
2. global `vars`
3. template `include_vars`
4. template `vars`

### Templates

The templates are rendered with Jinja2 using the global and local variables defined in the definition file. Any Jinja2 specific syntax can be used.

In addition to the [extra filters](#extra-jinja2-filters) the variable `omit` can be used in the templates. This concept is borrowed from Ansible and the purpose is to omit options from the DC file where a variable is not defined. In the following example the env variable `VAR2` will be omitted from the template if `my_var` was not defined in the definition file:

```yaml
services:
  foo:
    environment:
      - "VAR1=abc"
      - "VAR2={{ my_var|default(omit) }}"
    ...
```

Because of the omit functionality the renderer only renders YAML files, generic file types do not work.

### Examples

Examples can be found in the [`examples`](examples) directory. There are three stacks defined, one global stack and two user stacks. The user stacks define a _Nextloud_ and _Redis_ service. Both stacks depend on the global one, meaning those share a global _MariaDB_ and a reverse proxy.

## Extra Jinja2 Filters

In addition to the [Jinja built-in filters](http://jinja.pocoo.org/docs/2.10/templates/#builtin-filters) the following extra filters are implemented. The filter are based on the filter in Ansible:

Filter* | Description
--------|------------
`mandatory(msg)` | If the variable is not defined an error with a message `msg` will be thrown.
`regex_escape` | Escape special characters to safely use a string in a regex search.
`regex_findall(pattern[, ignorecase, multiline])` | Find all occurrences of regex matches.<br>Default values: `ignorecase=False`, `multiline=False`
`regex_replace(pattern, replacement[, ignorecase, multiline])` | Perform a regex search and replace operation.<br>Default values: `ignorecase=False`, `multiline=False`
`regex_search(pattern[, groups, ignorecase, multiline])` | Search with regex. If one or more match `groups` are specified the search result will be a list containing only those group matches. The groups are specified either by their position (e.g. `\1`) or by their name (e.g. foo: `\gfoo`).<br>Default values: `ignorecase=False`, `multiline=False`
`regex_contains(pattern[, ignorecase, multiline])` | Yields `true` if the string contains the given regex pattern.<br>Default values: `ignorecase=False`, `multiline=False`
`to_bool([default_value])` | Converts a string to a bool value. The `default_value` will be used if the string cannot be converted.
`to_yaml([indent, ...])` | Converts a value to YAML.<br>Default values: `indent=2`
`to_json([...])` | Converts a value to JSON.
`to_nice_json([indent])` | Converts a value to human readable JSON.<br>Default values: `indent=4`

> \* Arguments enclosed with brackets are optional

## Todo

* Add `pre_render` and `post_render` options
* Write more tests

## License

_Docker Compose Templer_ is released under the LGPL v3 License. See [LICENSE.txt](LICENSE.txt) for more information.
