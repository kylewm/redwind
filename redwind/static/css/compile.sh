#!/bin/sh

cat base.css skeleton.css layout.css pygments.css | cssmin > unified.min.css
