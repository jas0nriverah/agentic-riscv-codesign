(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x424 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x84 (bvadd ?x424 (_ bv0 32))))
(and (distinct ?x84 ?x424) true))))
(check-sat)
