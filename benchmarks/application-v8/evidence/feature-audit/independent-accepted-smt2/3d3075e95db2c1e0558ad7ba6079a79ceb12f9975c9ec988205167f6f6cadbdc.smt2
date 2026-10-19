; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x60 (bvadd independent_opaque_0 (_ bv264 32))))
(and (distinct ?x60 ?x60) true)))
(check-sat)
