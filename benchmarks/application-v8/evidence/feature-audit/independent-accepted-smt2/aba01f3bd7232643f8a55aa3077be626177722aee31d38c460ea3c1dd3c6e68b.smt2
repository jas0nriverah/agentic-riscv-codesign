; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x9 (bvadd independent_opaque_0 (_ bv4294966656 32))))
(and (distinct ?x9 ?x9) true)))
(check-sat)
