; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x7 (bvadd independent_opaque_0 (_ bv4294966984 32))))
(and (distinct ?x7 ?x7) true)))
(check-sat)
