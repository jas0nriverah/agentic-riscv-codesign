; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x45 (bvadd independent_opaque_0 (_ bv819 32))))
(and (distinct ?x45 ?x45) true)))
(check-sat)
