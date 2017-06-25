# South Africa's Constitution as Akoma Ntoso

This project generates [Akoma Ntoso](http://www.akomantoso.org/) markup versions of South Africa's constitution using the HTML output of the [MyConstitution.co.za](http://myconstitution.co.za) project.

## Running locally

1. Clone this repo (with ``--recursive`` for submodules)
2. Create a virtualenv: ``virtualenv --no-site-packages env``
3. Activate it: ``source env/bin/activate``
4. Install dependencies: ``pip install -r requirements.txt``
5. Generate XML and HTML: ``python transform.py``

# License

This code is licensed under an MIT license. The original constitution markdown and HTML are in the public domain. The generated XML and HTML files are also in the public domain.

Share the love.
