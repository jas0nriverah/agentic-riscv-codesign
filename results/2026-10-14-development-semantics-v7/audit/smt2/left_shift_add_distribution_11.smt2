(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x147 (bvshl y (_ bv11 32))))
(let ((?x143 (bvshl x (_ bv11 32))))
(let ((?x148 (bvadd ?x143 ?x147)))
(let ((?x19 (bvadd x y)))
(let ((?x146 (bvshl ?x19 (_ bv11 32))))
(and (distinct ?x146 ?x148) true)))))))
(check-sat)
