# Docker Compose Templer

This is a little Python3 utility that adds more dynamism to [Docker Compose or Docker Stack files](https://docs.docker.com/compose/compose-file/) by utilizing the [Jinja2 template engine](http://jinja.pocoo.org/).

Docker Compose (DC) files are quite static in nature. It is possible to use [variable substitution](https://docs.docker.com/compose/compose-file/#variable-substitution) to run slightly different container configurations based on a single DC file. This, however, doesn't allow complex variations in networks, volumes, etc. and proper code reuse. Therefore I decided to create this Python program to introduce Jinja2 templating to DC files. A _definition file_ says where to find the templates, what variables to use and where to put the rendered files.

The documentation on the Jinja2 syntax can be found [here](http://jinja.pocoo.org/docs/dev/templates/).

**Features:**

* templating using Jinja2
* using YAML syntax for definition and variable files
* monitoring of file changes and automatic rendering of templates (especially useful during development)
* using some [extra Jinja filters](#extra-jinja2-filters) (comply with Ansible filters)

**Table of contents:**

* [Installation](#installation)
* [Usage](#usage)
  * [Command line arguments](#command-line-arguments)
  * [Definition File](#definition-file)
  * [Templates](#templates)
  * [Examples](#examples)
* [Extra Jinja2 Filters](#extra-jinja2-filters)
* [Todo](#todo)
* [License](#license)

---

## Installation

Install directly from Github:

```sh
pip install git+https://github.com/Aisbergg/python-docker-compose-templer@v1.1.0
```

Install from PyPi:

```sh
pip install docker-compose-templer
```

If you like to use the optinal _auto render_ function then you have to install the [Pyinotify](https://github.com/seb-m/pyinotify) package as well:

```sh
pip install pyinotify
```

## Usage

### Command line arguments

```text
usage: docker-compose-templer [-a] [-f] [-h] [-v] [--version]
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
# (optional) define global variables to be used in all templates - can contain Jinja syntax
vars:
  some_global_var: foo
  another_global_var: "{{some_global_var}}bar" # will render to 'foobar'

# (optional) load global variables from YAML file(s) (order matters) - can contain Jinja syntax
include_vars:
  - path/to/file_1.yml
  - path/to/file_2.yml

# template definitions
templates:
  # first template
  - src: templates/my_template.yml.j2 # source file as Jinja2 template (Jinja syntax can be used on path)
    dest: stacks/s1/my_instance.yml   # path for resulting file (Jinja syntax can be used on path)
    include_vars: variables/s1.yml    # (optional) include local variables from YAML file(s)
    vars:                             # (optional) local variables for this template
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

Examples can be found in the [`examples`](examples) directory. There are three stacks defined, one global stack and two user stacks. The user stacks define a _Nextloud_ and _Redis_ service. Both stacks depend on the global one, meaning those share a global _MariaDB_ and a reverse proxy. To run this example execute the following command inside the `examples/` directory: `docker_compose_templer -f stack-global.yml stack-user1.yml stack-user2.yml`

## Extra Jinja2 Filters

In addition to the [Jinja built-in filters](http://jinja.pocoo.org/docs/latest/templates/#builtin-filters) the following extra filters are implemented. The filter are based on the filter in Ansible:

Filter                                                                   | Description
-------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
`mandatory(msg)`                                                         | If the variable is undefined an error with a message `msg` will be thrown.
`regex_escape()`                                                         | Escape special characters to safely use a string in a regex search.
`regex_findall(pattern, ignorecase=False, multiline=False)`              | Find all occurrences of regex matches.
`regex_replace(pattern, replacement, ignorecase=False, multiline=False)` | Perform a regex search and replace operation.
`regex_search(pattern, groups, ignorecase=False, multiline=False)`       | Search with regex. If one or more match `groups` are specified the search result will be a list containing only those group matches. The groups are specified either by their position (e.g. `\1`) or by their name (e.g. foo: `\gfoo`).
`regex_contains(pattern, ignorecase=False, multiline=False)`             | Yields `true` if the string contains the given regex pattern.
`to_bool(default_value=None)`                                            | Converts a string to a bool value. The `default_value` will be used if the string cannot be converted.
`to_yaml(indent=2, [...])`                                               | Converts a value to YAML.
`to_json([...])`                                                         | Converts a value to JSON.
`to_nice_json(indent=2, [...])`                                          | Converts a value to human readable JSON.

## Todo

* Add `pre_render` and `post_render` options
* Write more tests

## License

_Docker Compose Templer_ is released under the LGPL v3 License. See [LICENSE.txt](LICENSE.txt) for more information.
