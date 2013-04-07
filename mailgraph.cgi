#!/usr/bin/perl -w

# mailgraph -- postfix mail traffic statistics
# copyright (c) 2000-2007 ETH Zurich
# copyright (c) 2000-2007 David Schweikert <david@schweikert.ch>
# released under the GNU General Public License

# modified to include reject reasons by Martin Schuette <info@mschuette.name>

use RRDs;
use POSIX qw(uname);

my $VERSION = "1.14mod";

my $host = (POSIX::uname())[1];
my $scriptname = 'mailgraph.cgi';
my $xpoints = 540;
my $points_per_sample = 3;
my $ypoints = 160;
my $ypoints_err = 96;
my $rrd = 'mailgraph.rrd'; # path to where the RRD database is
my $rrd_virus = 'mailgraph_virus.rrd'; # path to where the Virus RRD database is
my $rrd_rejects = "mailgraph_rejects.rrd";
my $tmp_dir = '/tmp/mailgraph'; # temporary directory where to store the images

# note: the following ranges must match with the RRA ranges
# created in mailgraph.pl, otherwise the totals won't match.
my @graphs = (
	{ title => 'Last Day',   seconds => 3600*24,        },
	{ title => 'Last Week',  seconds => 3600*24*7,      },
	{ title => 'Last Month', seconds => 3600*24*7*5,     },
	{ title => 'Last Year',  seconds => 3600*24*7*5*12, },
);

my %color = (
	sent     => '000099', # rrggbb in hex
	received => '009900',
	rejected => 'AA0000', 
	bounced  => '000000',
	virus    => 'DDBB00',
	spam     => '999999',
	rej_userunknown => 'AAFFFF',
	rej_sender      => 'FFAAAA',
	rej_norelay     => 'AAFFAA',
	rej_policydw    => '555555',
	rej_helo        => '55FF55',
	rej_dnsbl       => 'FF55FF',
	rej_greylisted  => 'FFFF00',
	rej_greyblocked => '0000FF',
	rej_other       => 'CCCCCC',
);

sub rrd_graph(@)
{
	my ($range, $file, $ypoints, @rrdargs) = @_;
	my $step = $range*$points_per_sample/$xpoints;
	# choose carefully the end otherwise rrd will maybe pick the wrong RRA:
	my $end  = time; $end -= $end % $step;
	my $date = localtime(time);
	$date =~ s|:|\\:|g unless $RRDs::VERSION < 1.199908;

	my ($graphret,$xs,$ys) = RRDs::graph($file,
		'--imgformat', 'PNG',
		'--width', $xpoints,
		'--height', $ypoints,
		'--start', "-$range",
		'--end', $end,
		'--vertical-label', 'msgs/min',
		'--lower-limit', 0,
		'--units-exponent', 0, # don't show milli-messages/s
		'--lazy',
		'--color', 'SHADEA#ffffff',
		'--color', 'SHADEB#ffffff',
		'--color', 'BACK#ffffff',

		$RRDs::VERSION < 1.2002 ? () : ( '--slope-mode'),

		@rrdargs,

		'COMMENT:['.$date.']\r',
	);

	my $ERR=RRDs::error;
	die "ERROR: $ERR\n" if $ERR;
}

sub graph($$)
{
	my ($range, $file) = @_;
	my $step = $range*$points_per_sample/$xpoints;
	rrd_graph($range, $file, $ypoints,
		"DEF:sent=$rrd:sent:AVERAGE",
		"DEF:msent=$rrd:sent:MAX",
		"CDEF:rsent=sent,60,*",
		"CDEF:rmsent=msent,60,*",
		"CDEF:dsent=sent,UN,0,sent,IF,$step,*",
		"CDEF:ssent=PREV,UN,dsent,PREV,IF,dsent,+",
		"AREA:rsent#$color{sent}:Sent    ",
		'GPRINT:ssent:MAX:total\: %8.0lf msgs',
		'GPRINT:rsent:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmsent:MAX:max\: %4.0lf msgs/min\l',

		"DEF:recv=$rrd:recv:AVERAGE",
		"DEF:mrecv=$rrd:recv:MAX",
		"CDEF:rrecv=recv,60,*",
		"CDEF:rmrecv=mrecv,60,*",
		"CDEF:drecv=recv,UN,0,recv,IF,$step,*",
		"CDEF:srecv=PREV,UN,drecv,PREV,IF,drecv,+",
		"LINE2:rrecv#$color{received}:Received",
		'GPRINT:srecv:MAX:total\: %8.0lf msgs',
		'GPRINT:rrecv:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrecv:MAX:max\: %4.0lf msgs/min\l',

		# include thin reject-line into sent/receive graph
		"DEF:rejected=$rrd:rejected:AVERAGE",
		"DEF:mrejected=$rrd:rejected:MAX",
		"CDEF:rrejected=rejected,60,*",
		"CDEF:drejected=rejected,UN,0,rejected,IF,$step,*",
		"CDEF:srejected=PREV,UN,drejected,PREV,IF,drejected,+",
		"CDEF:rmrejected=mrejected,60,*",
		"LINE1:rrejected#$color{rejected}:Rejected",
		'GPRINT:srejected:MAX:total\: %8.0lf msgs',
		'GPRINT:rrejected:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrejected:MAX:max\: %4.0lf msgs/min\l',
	);
}

sub graph_err($$)
{
	my ($range, $file) = @_;
	my $step = $range*$points_per_sample/$xpoints;
	# new graph layout:
	# reject-reasons are stacked upward,
	# virus/spam/bounce stacked negative and downwards,
	rrd_graph($range, $file, $ypoints,
		"DEF:rej_userunknown=$rrd_rejects:rej_userunknown:AVERAGE",
		"DEF:mrej_userunknown=$rrd_rejects:rej_userunknown:MAX",
		"CDEF:rrej_userunknown=rej_userunknown,60,*",
		"CDEF:drej_userunknown=rej_userunknown,UN,0,rej_userunknown,IF,$step,*",
		"CDEF:srej_userunknown=PREV,UN,drej_userunknown,PREV,IF,drej_userunknown,+",
		"CDEF:rmrej_userunknown=mrej_userunknown,60,*",
		"AREA:rrej_userunknown#$color{rej_userunknown}:user unknown  ",
		'GPRINT:srej_userunknown:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_userunknown:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_userunknown:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_sender=$rrd_rejects:rej_sender:AVERAGE",
		"DEF:mrej_sender=$rrd_rejects:rej_sender:MAX",
		"CDEF:rrej_sender=rej_sender,60,*",
		"CDEF:drej_sender=rej_sender,UN,0,rej_sender,IF,$step,*",
		"CDEF:srej_sender=PREV,UN,drej_sender,PREV,IF,drej_sender,+",
		"CDEF:rmrej_sender=mrej_sender,60,*",
		"STACK:rrej_sender#$color{rej_sender}:sender        ",
		'GPRINT:srej_sender:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_sender:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_sender:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_norelay=$rrd_rejects:rej_norelay:AVERAGE",
		"DEF:mrej_norelay=$rrd_rejects:rej_norelay:MAX",
		"CDEF:rrej_norelay=rej_norelay,60,*",
		"CDEF:drej_norelay=rej_norelay,UN,0,rej_norelay,IF,$step,*",
		"CDEF:srej_norelay=PREV,UN,drej_norelay,PREV,IF,drej_norelay,+",
		"CDEF:rmrej_norelay=mrej_norelay,60,*",
		"STACK:rrej_norelay#$color{rej_norelay}:no Relaying   ",
		'GPRINT:srej_norelay:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_norelay:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_norelay:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_dnsbl=$rrd_rejects:rej_dnsbl:AVERAGE",
		"DEF:mrej_dnsbl=$rrd_rejects:rej_dnsbl:MAX",
		"CDEF:rrej_dnsbl=rej_dnsbl,60,*",
		"CDEF:drej_dnsbl=rej_dnsbl,UN,0,rej_dnsbl,IF,$step,*",
		"CDEF:srej_dnsbl=PREV,UN,drej_dnsbl,PREV,IF,drej_dnsbl,+",
		"CDEF:rmrej_dnsbl=mrej_dnsbl,60,*",
		"STACK:rrej_dnsbl#$color{rej_dnsbl}:DNS RBL       ",
		'GPRINT:srej_dnsbl:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_dnsbl:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_dnsbl:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_policydw=$rrd_rejects:rej_policydw:AVERAGE",
		"DEF:mrej_policydw=$rrd_rejects:rej_policydw:MAX",
		"CDEF:rrej_policydw=rej_policydw,60,*",
		"CDEF:drej_policydw=rej_policydw,UN,0,rej_policydw,IF,$step,*",
		"CDEF:srej_policydw=PREV,UN,drej_policydw,PREV,IF,drej_policydw,+",
		"CDEF:rmrej_policydw=mrej_policydw,60,*",
		"STACK:rrej_policydw#$color{rej_policydw}:policyd-weight",
		'GPRINT:srej_policydw:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_policydw:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_policydw:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_helo=$rrd_rejects:rej_helo:AVERAGE",
		"DEF:mrej_helo=$rrd_rejects:rej_helo:MAX",
		"CDEF:rrej_helo=rej_helo,60,*",
		"CDEF:drej_helo=rej_helo,UN,0,rej_helo,IF,$step,*",
		"CDEF:srej_helo=PREV,UN,drej_helo,PREV,IF,drej_helo,+",
		"CDEF:rmrej_helo=mrej_helo,60,*",
		"STACK:rrej_helo#$color{rej_helo}:HELO          ",
		'GPRINT:srej_helo:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_helo:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_helo:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_greylisted=$rrd_rejects:rej_greylisted:AVERAGE",
		"DEF:mrej_greylisted=$rrd_rejects:rej_greylisted:MAX",
		"CDEF:rrej_greylisted=rej_greylisted,60,*",
		"CDEF:drej_greylisted=rej_greylisted,UN,0,rej_greylisted,IF,$step,*",
		"CDEF:srej_greylisted=PREV,UN,drej_greylisted,PREV,IF,drej_greylisted,+",
		"CDEF:rmrej_greylisted=mrej_greylisted,60,*",
		"STACK:rrej_greylisted#$color{rej_greylisted}:Greylisted    ",
		'GPRINT:srej_greylisted:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_greylisted:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_greylisted:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_greyblocked=$rrd_rejects:rej_greyblocked:AVERAGE",
		"DEF:mrej_greyblocked=$rrd_rejects:rej_greyblocked:MAX",
		"CDEF:rrej_greyblocked=rej_greyblocked,60,*",
		"CDEF:drej_greyblocked=rej_greyblocked,UN,0,rej_greyblocked,IF,$step,*",
		"CDEF:srej_greyblocked=PREV,UN,drej_greyblocked,PREV,IF,drej_greyblocked,+",
		"CDEF:rmrej_greyblocked=mrej_greyblocked,60,*",
		"STACK:rrej_greyblocked#$color{rej_greyblocked}:retry too fast",
		'GPRINT:srej_greyblocked:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_greyblocked:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_greyblocked:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rej_other=$rrd_rejects:rej_other:AVERAGE",
		"DEF:mrej_other=$rrd_rejects:rej_other:MAX",
		"CDEF:rrej_other=rej_other,60,*",
		"CDEF:drej_other=rej_other,UN,0,rej_other,IF,$step,*",
		"CDEF:srej_other=PREV,UN,drej_other,PREV,IF,drej_other,+",
		"CDEF:rmrej_other=mrej_other,60,*",
		"STACK:rrej_other#$color{rej_other}:Other rejects ",
		'GPRINT:srej_other:MAX:total\: %8.0lf msgs',
		'GPRINT:rrej_other:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrej_other:MAX:max\: %4.0lf msgs/min\l',
		
		"DEF:rejected=$rrd:rejected:AVERAGE",
		"DEF:mrejected=$rrd:rejected:MAX",
		"CDEF:rrejected=rejected,60,*",
		"CDEF:drejected=rejected,UN,0,rejected,IF,$step,*",
		"CDEF:srejected=PREV,UN,drejected,PREV,IF,drejected,+",
		"CDEF:rmrejected=mrejected,60,*",
		"LINE1:rrejected#$color{rejected}:Total rejected",
		'GPRINT:srejected:MAX:total\: %8.0lf msgs',
		'GPRINT:rrejected:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmrejected:MAX:max\: %4.0lf msgs/min\l',
		
		# move spam to bottom of stack
		"DEF:spam=$rrd_virus:spam:AVERAGE",
		"DEF:mspam=$rrd_virus:spam:MAX",
		"CDEF:rspam=spam,60,*",
		"CDEF:negrspam=rspam,-1,*",
		"CDEF:dspam=spam,UN,0,spam,IF,$step,*",
		"CDEF:sspam=PREV,UN,dspam,PREV,IF,dspam,+",
		"CDEF:rmspam=mspam,60,*",
		"AREA:negrspam#$color{spam}:Spam detected ",
		'GPRINT:sspam:MAX:total\: %8.0lf msgs',
		'GPRINT:rspam:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmspam:MAX:max\: %4.0lf msgs/min\l',

		"DEF:bounced=$rrd:bounced:AVERAGE",
		"DEF:mbounced=$rrd:bounced:MAX",
		"CDEF:rbounced=bounced,60,*",
		"CDEF:negrbounced=rbounced,-1,*",
		"CDEF:dbounced=bounced,UN,0,bounced,IF,$step,*",
		"CDEF:sbounced=PREV,UN,dbounced,PREV,IF,dbounced,+",
		"CDEF:rmbounced=mbounced,60,*",
		"STACK:negrbounced#$color{bounced}:Bounced       ",
		'GPRINT:sbounced:MAX:total\: %8.0lf msgs',
		'GPRINT:rbounced:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmbounced:MAX:max\: %4.0lf msgs/min\l',

		"DEF:virus=$rrd_virus:virus:AVERAGE",
		"DEF:mvirus=$rrd_virus:virus:MAX",
		"CDEF:rvirus=virus,60,*",
		"CDEF:negrvirus=rvirus,-1,*",
		"CDEF:dvirus=virus,UN,0,virus,IF,$step,*",
		"CDEF:svirus=PREV,UN,dvirus,PREV,IF,dvirus,+",
		"CDEF:rmvirus=mvirus,60,*",
		"STACK:negrvirus#$color{virus}:Viruses       ",
		'GPRINT:svirus:MAX:total\: %8.0lf msgs',
		'GPRINT:rvirus:AVERAGE:avg\: %5.2lf msgs/min',
		'GPRINT:rmvirus:MAX:max\: %4.0lf msgs/min\l',
	);
}

sub print_html()
{
	print "Content-Type: text/html\n\n";

	print <<HEADER;
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>Mail statistics for $host</title>
<meta http-equiv="Refresh" content="300" />
<meta http-equiv="Pragma" content="no-cache" />
<style type="text/css">
*     { margin: 0; padding: 0 }
body  { width: 630px; background-color: white;
       font-family: sans-serif;
       font-size: 12pt;
       margin: 5px }
h1    { margin-top: 20px; margin-bottom: 30px;
        text-align: center }
h2    { background-color: #ddd;
       padding: 2px 0 2px 4px }
hr    { height: 1px;
       border: 0;
       border-top: 1px solid #aaa }
table { border: 0px; width: 100% }
img   { border: 0 }
a     { text-decoration: none; color: #00e }
a:hover { text-decoration: underline; }
#jump    { margin: 0 0 10px 4px }
#jump li { list-style: none; display: inline;
           font-size: 90%; }
#jump li:after            { content: "|"; }
#jump li:last-child:after { content: ""; }
</style>
</head>
<body>
HEADER

	print "<h1>Mail statistics for $host</h1>\n";

	print "<ul id=\"jump\">\n";
	for my $n (0..$#graphs) {
		print "  <li><a href=\"#G$n\">$graphs[$n]{title}</a>&nbsp;</li>\n";
	}
	print "</ul>\n";

	for my $n (0..$#graphs) {
		print "<h2 id=\"G$n\">$graphs[$n]{title}</h2>\n";
		print "<p><img src=\"$scriptname?${n}-n\" alt=\"mailgraph\"/><br/>\n";
		print "<img src=\"$scriptname?${n}-e\" alt=\"mailgraph\"/></p>\n";
	}

	print <<FOOTER;
<hr/>
<table><tr><td>
<a href="http://mailgraph.schweikert.ch/">Mailgraph</a> $VERSION
by <a href="http://david.schweikert.ch/">David Schweikert</a></td>
<td align="right">
<a href="http://oss.oetiker.ch/rrdtool/"><img src="http://oss.oetiker.ch/rrdtool/.pics/rrdtool.gif" alt="" width="120" height="34"/></a>
</td></tr></table>
</body></html>
FOOTER
}

sub send_image($)
{
	my ($file)= @_;

	-r $file or do {
		print "Content-type: text/plain\n\nERROR: can't find $file\n";
		exit 1;
	};

	print "Content-type: image/png\n" unless $ARGV[0];
	print "Content-length: ".((stat($file))[7])."\n" unless $ARGV[0];
	print "\n" unless $ARGV[0];
	open(IMG, $file) or die;
	my $data;
	print $data while read(IMG, $data, 16384)>0;
}

sub main()
{
	my $uri = $ENV{REQUEST_URI} || '';
	$uri =~ s/\/[^\/]+$//;
	$uri =~ s/\//,/g;
	$uri =~ s/(\~|\%7E)/tilde,/g;
	mkdir $tmp_dir, 0777 unless -d $tmp_dir;
	mkdir "$tmp_dir/$uri", 0777 unless -d "$tmp_dir/$uri";

	my $img = $ARGV[0] || $ENV{QUERY_STRING};
	if(defined $img and $img =~ /\S/) {
		if($img =~ /^(\d+)-n$/) {
			my $file = "$tmp_dir/$uri/mailgraph_$1.png";
			graph($graphs[$1]{seconds}, $file);
			send_image($file);
		}
		elsif($img =~ /^(\d+)-e$/) {
			my $file = "$tmp_dir/$uri/mailgraph_$1_err.png";
			graph_err($graphs[$1]{seconds}, $file);
			send_image($file);
		}
		else {
			die "ERROR: invalid argument\n";
		}
	}
	else {
		print_html;
	}
}

main;
