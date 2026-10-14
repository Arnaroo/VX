# GtkD, as VX's binaries are built with it

VX is based in part on works of the GtkD project (http://gtkd.org).

VX's binaries for Linux, macOS and Windows link GtkD 3.10.0 (https://github.com/gtkd-developers/GtkD, the release
v3.10.0), the D binding of GTK 3, statically. GtkD is provided under the GNU Lesser General Public License, version 3
or later, with the GtkD project's exceptions (the file COPYING of GtkD's source). Those exceptions permit static
linking, and ask that a change made to GtkD for an application be provided under the terms of the LGPL. VX's build
changes GtkD in one place. The change is given here in full and is provided under the LGPL, version 3 or later.

## The change

In `generated/gtkd/gobject/ObjectG.d` of GtkD 3.10.0, in the class `ObjectG`, the block below is inserted immediately
before the existing declaration

```d
	/** */
	T opCast(T)()
```

The inserted block:

```d
	/** A const overload of opCast, added for VX's build: a cast to a parent
	 *  class only (under const it cannot take the underlying GObject's
	 *  reference). LDC 1.42 and later (D front end 2.112 and later) hash
	 *  the values of an associative array through cast(Object), which
	 *  looks for opCast on a const reference. */
	T opCast(T)() const
	{
		if ( !this )
			return null;
		return cast(T)super;
	}

```

Nothing else in GtkD is changed. Without the block, a program that keeps GTK widgets as the values of an associative
array does not compile against GtkD 3.10.0 with LDC 1.42 or later (the error: a mutable method opCast is not callable
using a const object).
