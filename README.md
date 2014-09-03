3D Dust Map Webpage
===================

A webpage for disseminating the Bayestar 3D dust map
and the papers describing it. The page is broken down
into three sub-pages:

  1. Query map
  2. Download map
  3. Read paper(s)

A cover page connects these three pages.

Query map
---------

This functionality is being implemented using Ajax
queries. It is envisioned that there will be a worker
process on the backend processing query requests.

Each time a query is made through Ajax, it will be
added by the backend to a Queue, which the worker
process (using the multiprocess module) will be
listening to. The worker will query the requested
part of the map, and return the relevant data. This
may consist of a link to a plot, as well as samples
from the Markov Chain. The main process will then
send this data back to the user, where front-end
jQuery and D3 will display it.

Download Map
------------

TODO.

Will probably be a set of download links, both for
data and software (python, possibly also IDL) for
reading the data cube. Will include basic information
on how to access and properly interpret the data.

Read Paper(s)
-------------

Will contain a link to the map release paper, and
possibly links to other papers related to the map.

One possibility is including a set of linked thumbnails,
like in [Greg's home page](greg.ory.gr/een#papers).

Credit
------

The 3D dust map originates from the Finkbeiner
research group at Harvard Astronomy. The primary
contributors to the project are Greg Green, Eddie
Schlafly and Doug Finkbeiner. Several others, including
Mario Juric (now at LSST) and Hans-Walter Rix (MPIA)
have also contributed significantly to the effort.
